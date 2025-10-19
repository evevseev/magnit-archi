#!/usr/bin/env python3
"""
Validate an Archi Grafico repository structure and contents.

Checks:
- Required structure: model/, images/ (optional), model/folder.xml, and the 9 top-level folders each with folder.xml
- Filenames: <Class>_<id>.xml, root element matches class, root @id matches filename id
- Hrefs: Format Filename.xml#id (no folder segments), target file exists, target root @id equals fragment
- Relationships: Require single <source> and <target> with xsi:type and href
- Diagrams: ArchimateDiagramModel/SketchModel structure, children ids, connections source/target ids, archimateElement/Relationship hrefs
- Optional: Validate class placement in top-level default folder using types/catalog.json if present
- Optional: Enforce id format id-<32 hex>
- Optional: Load model with Archi CLI for integration check

Usage:
  python3 scripts/validate_grafico.py --repo /path/to/repo [--archi "/Applications/Archi.app/Contents/MacOS/Archi"] [--strict-ids]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


ARCHIMATE_NS = "http://www.archimatetool.com/archimate"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
NSMAP = {"archimate": ARCHIMATE_NS, "xsi": XSI_NS}

TOP_FOLDERS = [
    "Strategy",
    "Business",
    "Application",
    "Technology",
    "Motivation",
    "Implementation_Migration",
    "Other",
    "Relations",
    "Diagrams",
]

ID_RECOMMENDED = re.compile(r"^id-[0-9A-Fa-f]{32}$")
FILENAME_RE = re.compile(r"^([A-Za-z0-9_]+)_(.+)\.xml$")


def localname(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def parse_xml(path: Path) -> ET.Element:
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as e:
        raise ValueError(f"XML parse error in {path}: {e}")


def read_catalog(repo: Path) -> Tuple[Dict[str, str], set, set, set]:
    """Return (class_to_folder, elements, relationships, diagrams). If no catalog, return empties."""
    catalog_path = repo / "types" / "catalog.json"
    if not catalog_path.is_file():
        return {}, set(), set(), set()
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to read types/catalog.json: {e}")
    class_to_folder: Dict[str, str] = {}
    elements, relationships, diagrams = set(), set(), set()
    for e in data.get("elements", []):
        cls = e.get("class"); folder = e.get("defaultFolder")
        if cls and folder:
            class_to_folder[cls] = folder
            elements.add(cls)
    for r in data.get("relationships", []):
        cls = r.get("class"); folder = r.get("defaultFolder")
        if cls and folder:
            class_to_folder[cls] = folder
            relationships.add(cls)
    for d in data.get("diagrams", []):
        cls = d.get("class"); folder = d.get("defaultFolder")
        if cls and folder:
            class_to_folder[cls] = folder
            diagrams.add(cls)
    return class_to_folder, elements, relationships, diagrams


class Validator:
    def __init__(self, repo_root: Path, archi_bin: Optional[Path], strict_ids: bool) -> None:
        self.repo = repo_root
        self.model_dir = self.repo / "model"
        self.archi_bin = archi_bin
        self.strict_ids = strict_ids
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.class_to_folder, self.element_classes, self.relationship_classes, self.diagram_classes = read_catalog(self.repo)
        self.relation_rules = self._read_relationship_rules()
        self.groups = self.relation_rules.get("groups", {}) if self.relation_rules else {}
        # Cache: basename -> full path
        self.basename_to_path: Dict[str, Path] = {}
        # Cache: full path -> (root_local_name, id)
        self.file_meta: Dict[Path, Tuple[str, str]] = {}

    def fail(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def check_structure(self) -> None:
        if not self.model_dir.is_dir():
            self.fail(f"Missing required folder: {self.model_dir}")
            return
        if not (self.model_dir / "folder.xml").is_file():
            self.fail(f"Missing required file: {self.model_dir / 'folder.xml'}")
        for f in TOP_FOLDERS:
            d = self.model_dir / f
            if not d.is_dir():
                self.fail(f"Missing top-level folder: {d}")
                continue
            if not (d / "folder.xml").is_file():
                self.fail(f"Missing folder.xml in: {d}")

        # Root model folder.xml
        fx = self.model_dir / "folder.xml"
        if fx.is_file():
            try:
                root = parse_xml(fx)
                if localname(root.tag) != "model" or root.tag.split("}")[0].strip("{") != ARCHIMATE_NS:
                    self.fail(f"model/folder.xml root must be archimate:model (got {root.tag})")
            except Exception as e:
                self.fail(str(e))

        # Each subfolder folder.xml root
        for f in TOP_FOLDERS:
            fx = self.model_dir / f / "folder.xml"
            if fx.is_file():
                try:
                    root = parse_xml(fx)
                    if localname(root.tag) != "Folder":
                        self.fail(f"{fx} root must be archimate:Folder (got {root.tag})")
                except Exception as e:
                    self.fail(str(e))

    def index_files(self) -> None:
        for p in self.model_dir.rglob("*.xml"):
            if p.name == "folder.xml":
                continue
            self.basename_to_path[p.name] = p
            try:
                root = parse_xml(p)
            except Exception as e:
                self.fail(str(e))
                continue
            rid = root.get("id") or ""
            if not rid:
                self.fail(f"Missing @id on root: {p}")
            self.file_meta[p] = (localname(root.tag), rid)

    def check_files_and_ids(self) -> None:
        for p, (root_local, rid) in self.file_meta.items():
            base = p.name
            m = FILENAME_RE.match(base)
            if not m:
                self.fail(f"Invalid filename pattern (expected <Class>_<id>.xml): {p}")
                continue
            cls, fid = m.group(1), m.group(2)
            # Root must match class except special root names already excluded from standalone files
            if cls not in ("ArchimateDiagramModel", "SketchModel") and root_local != cls:
                self.fail(f"Root element ({root_local}) does not match class ({cls}) in filename: {p}")
            if rid != fid:
                self.fail(f"Root @id ({rid}) does not match filename id ({fid}): {p}")
            if self.strict_ids and not ID_RECOMMENDED.match(fid):
                self.fail(f"ID not in recommended form id-<32 hex>: {fid} ({p})")
            # Optional: default folder check if catalog present
            if self.class_to_folder:
                # Find immediate top-level folder name under model/
                try:
                    rel = p.relative_to(self.model_dir)
                    top = rel.parts[0]
                except ValueError:
                    top = None
                expected = self.class_to_folder.get(cls)
                if expected and top and expected != top:
                    self.fail(f"Class {cls} expected in folder '{expected}', found in '{top}': {p}")

            # EOL check (warn): no CR characters
            try:
                data = p.read_bytes()
                if b"\r" in data:
                    self.warn(f"CR characters found (non-UNIX newlines): {p}")
            except Exception:
                pass

    def _resolve_href(self, href: str) -> Tuple[Optional[Path], Optional[str]]:
        m = re.match(r"^([^/]+\.xml)#(.+)$", href)
        if not m:
            return None, None
        fname, frag = m.group(1), m.group(2)
        tgt = self.basename_to_path.get(fname)
        return tgt, frag

    def check_hrefs(self) -> None:
        for p in self.file_meta.keys():
            try:
                root = parse_xml(p)
            except Exception:
                continue
            for elem in root.iter():
                href = elem.get("href")
                if href is None:
                    continue
                tgt, frag = self._resolve_href(href)
                if tgt is None or frag is None:
                    self.fail(f"Invalid href (must be Filename.xml#id, no folder segments): {href} in {p}")
                    continue
                # target file id must equal fragment
                meta = self.file_meta.get(tgt)
                if not meta:
                    # parse on demand if not indexed (should be indexed)
                    try:
                        troot = parse_xml(tgt)
                        trid = troot.get("id") or ""
                        meta = (localname(troot.tag), trid)
                        self.file_meta[tgt] = meta
                    except Exception as e:
                        self.fail(f"Failed to parse target of href {href}: {e}")
                        continue
                _, trid = meta
                if frag != trid:
                    self.fail(f"Href id ({frag}) does not match target root @id ({trid}): {href} (in {p})")

    def check_relationships(self) -> None:
        for p, (root_local, _) in self.file_meta.items():
            if not root_local.endswith("Relationship"):
                continue
            root = parse_xml(p)
            # Children named source/target (no namespace) with href and xsi:type
            src_elems = [e for e in list(root) if localname(e.tag) == "source"]
            tgt_elems = [e for e in list(root) if localname(e.tag) == "target"]
            if len(src_elems) != 1:
                self.fail(f"Relationship missing single <source>: {p}")
            if len(tgt_elems) != 1:
                self.fail(f"Relationship missing single <target>: {p}")
            for lab, coll in ("source", src_elems), ("target", tgt_elems):
                if not coll:
                    continue
                e = coll[0]
                if not e.get("href"):
                    self.fail(f"Relationship {lab} missing @href: {p}")
                if not e.get(f"{{{XSI_NS}}}type"):
                    self.fail(f"Relationship {lab} missing @xsi:type: {p}")

            # Rule-based validity (if relationships.json present)
            if self.relation_rules:
                src_type = src_elems[0].get(f"{{{XSI_NS}}}type") or ""
                tgt_type = tgt_elems[0].get(f"{{{XSI_NS}}}type") or ""
                # Remove prefix archimate:
                if ":" in src_type:
                    src_type = src_type.split(":", 1)[1]
                if ":" in tgt_type:
                    tgt_type = tgt_type.split(":", 1)[1]
                if not self._is_relationship_allowed(root_local, src_type, tgt_type):
                    self.fail(
                        f"Relationship {root_local} not allowed between {src_type} and {tgt_type}: {p}"
                    )

    def check_diagrams(self) -> None:
        for p, (root_local, _) in self.file_meta.items():
            if root_local not in ("ArchimateDiagramModel", "SketchModel"):
                continue
            root = parse_xml(p)
            # Collect diagram object ids (children of any type)
            ids = set()
            for child in root.findall(".//", NSMAP):
                if child.get("id") and localname(child.tag) in (
                    "DiagramModelArchimateObject",
                    "DiagramModelNote",
                    "DiagramModelImage",
                    "DiagramModelGroup",
                    "DiagramModelReference",
                ):
                    ids.add(child.get("id"))
            # Connections via xsi:type=DiagramModelArchimateConnection
            for conn in root.findall(".//*", NSMAP):
                if conn.get(f"{{{XSI_NS}}}type") == "archimate:DiagramModelArchimateConnection":
                    sid = conn.get("source"); tid = conn.get("target")
                    if not sid or sid not in ids:
                        self.fail(f"Diagram connection source not found among children ids: {sid} in {p}")
                    if not tid or tid not in ids:
                        self.fail(f"Diagram connection target not found among children ids: {tid} in {p}")
                    # Must contain archimateRelationship child with href
                    found_rel = False
                    for ch in conn:
                        if localname(ch.tag) == "archimateRelationship":
                            found_rel = True
                            if not ch.get("href"):
                                self.fail(f"Diagram connection missing archimateRelationship/@href in {p}")
                            # Optional: validate relationship type against source/target element types using rules
                            if self.relation_rules:
                                rtype = ch.get(f"{{{XSI_NS}}}type") or ""
                                if ":" in rtype:
                                    rtype = rtype.split(":", 1)[1]
                                # Lookup the diagram object elements for source/target ids
                                sid = conn.get("source"); tid = conn.get("target")
                                src_elem_type = self._diagram_object_element_type(root, sid)
                                tgt_elem_type = self._diagram_object_element_type(root, tid)
                                if rtype and src_elem_type and tgt_elem_type:
                                    if not self._is_relationship_allowed(rtype, src_elem_type, tgt_elem_type):
                                        self.fail(
                                            f"Diagram connection {rtype} not allowed between {src_elem_type} and {tgt_elem_type} in {p}"
                                        )
                    if not found_rel:
                        self.fail(f"Diagram connection missing <archimateRelationship> in {p}")
            # Each DiagramModelArchimateObject needs bounds and archimateElement href
            for dmo in root.findall(".//*", NSMAP):
                if dmo.get(f"{{{XSI_NS}}}type") == "archimate:DiagramModelArchimateObject":
                    if dmo.find("bounds") is None:
                        self.fail(f"DiagramModelArchimateObject missing <bounds> in {p}")
                    ael = dmo.find("archimateElement")
                    if ael is None or not ael.get("href"):
                        self.fail(f"DiagramModelArchimateObject missing archimateElement/@href in {p}")

    def _diagram_object_element_type(self, root: ET.Element, dmo_id: Optional[str]) -> Optional[str]:
        if not dmo_id:
            return None
        for dmo in root.findall(".//*", NSMAP):
            if dmo.get("id") == dmo_id and dmo.get(f"{{{XSI_NS}}}type") == "archimate:DiagramModelArchimateObject":
                el = dmo.find("archimateElement")
                if el is None:
                    return None
                t = el.get(f"{{{XSI_NS}}}type") or ""
                if ":" in t:
                    t = t.split(":", 1)[1]
                return t
        return None

    def _read_relationship_rules(self) -> Dict[str, Any]:
        p = self.repo / "types" / "relationships.json"
        if not p.is_file():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            self.warn(f"Failed to read relationships.json: {e}")
            return {}

    def _is_relationship_allowed(self, rtype: str, src: str, tgt: str) -> bool:
        # If no rules, allow
        if not self.relation_rules:
            return True
        rules = self.relation_rules.get("rules", [])
        groups: Dict[str, List[str]] = self.relation_rules.get("groups", {})

        def in_group(name: str, cls: str) -> bool:
            return cls in groups.get(name, [])

        def match_side(rule_key_class: Optional[str], rule_key_group: Optional[str], actual: str) -> bool:
            if rule_key_class and rule_key_class == actual:
                return True
            if rule_key_group:
                if rule_key_group == "*":
                    return True
                if in_group(rule_key_group, actual):
                    return True
            return False

        for rule in rules:
            if rule.get("relationship") not in (rtype, "*"):
                continue
            # sameClass rule enforces src==tgt
            same_class = bool(rule.get("sameClass"))
            if same_class and src != tgt:
                continue
            if match_side(rule.get("sourceClass"), rule.get("sourceGroup"), src) and \
               match_side(rule.get("targetClass"), rule.get("targetGroup"), tgt):
                return True
        # No matching rule found; if there's any rule for this relationship type, then it's forbidden by omission.
        # If there are no rules for this type, return True to be permissive.
        any_for_type = any(r.get("relationship") == rtype for r in rules)
        return not any_for_type

    def optional_archi_load(self) -> None:
        if not self.archi_bin:
            return
        archi = str(self.archi_bin)
        if not os.access(archi, os.X_OK):
            self.fail(f"Archi binary not executable: {archi}")
            return
        try:
            proc = subprocess.run(
                [archi, "-application", "com.archimatetool.commandline.app", "-consoleLog", "-nosplash",
                 "--modelrepository.loadModel", str(self.repo)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False
            )
            out = proc.stdout
            if proc.returncode != 0:
                self.fail(f"Archi CLI returned code {proc.returncode}")
            if re.search(r"Exception|Unresolved|Error loading model", out, re.IGNORECASE):
                self.fail("Archi CLI reported errors/unresolved objects")
        except Exception as e:
            self.fail(f"Failed to run Archi CLI: {e}")

    def run(self) -> int:
        self.check_structure()
        if self.errors:
            self._report()
            return 1
        self.index_files()
        self.check_files_and_ids()
        self.check_hrefs()
        self.check_relationships()
        self.check_diagrams()
        self.optional_archi_load()
        return self._report()

    def _report(self) -> int:
        for w in self.warnings:
            print(f"WARN: {w}", file=sys.stderr)
        if self.errors:
            for e in self.errors:
                print(f"FAIL: {e}", file=sys.stderr)
            print(f"Validation completed with {len(self.errors)} error(s).", file=sys.stderr)
            return 1
        print("Validation passed.")
        return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Validate an Archi Grafico repository")
    ap.add_argument("--repo", "-r", required=True, help="Path to Grafico repository root")
    ap.add_argument("--archi", "-a", help="Path to Archi binary to attempt loading the model (optional)")
    ap.add_argument("--strict-ids", action="store_true", help="Enforce id-<32 hex> id format")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    archi_bin = Path(args.archi).resolve() if args.archi else None
    v = Validator(repo, archi_bin, args.strict_ids)
    return v.run()


if __name__ == "__main__":
    sys.exit(main())
