# Guide for LLMs: Creating Correct Grafico Projects for Archi

This guide provides precise, implementation‑aligned instructions for generating Archi Grafico projects (Git‑friendly Archi file collections) that Archi and compatible tools can load without errors. It focuses on structure, file naming, serialization rules, and parameters with valid values. Follow these rules strictly. Do not guess or invent fields.

Important: Do not handcraft arbitrary XML schemas. Use Archi’s EMF model (com.archimatetool.model) semantics and serialization conventions. If you cannot programmatically emit EMF XML, adhere to the constraints below exactly.

## Repository Layout

- Root
  - `.git/` — standard Git metadata (recommended; importer expects a repo context)
  - `model/` — required; contains the model structure and objects as XML files
  - `images/` — optional; contains external image assets used by the model

Reserved/known filenames in the repo root (do not create unless you know what you’re doing):
- `secure_credentials`, `secure_ssh_credentials`, `secure_proxy_credentials` — optional files used by some tools; not part of Grafico content
- `.git/` and any tool‑specific temporary files (e.g., `.git/temp.archimate`) are managed by tools, not by Grafico content

## Model Directory Structure

- Required top‑level file: `model/folder.xml`
  - Must serialize the root `IArchimateModel` object
  - If missing, importers treat the project as empty

- Required top‑level subfolders in `model/` (names must match exactly):
  - `Strategy`
  - `Business`
  - `Application`
  - `Technology`
  - `Motivation`
  - `Implementation_Migration`
  - `Other`
  - `Relations`
  - `Diagrams`

- Every folder (including `model/` and any nested folder) must contain a `folder.xml` that serializes that folder’s object (`IFolder` for non‑root folders, `IArchimateModel` for `model/`).

- Nested/user folders:
  - If a folder is of type `USER` (i.e., user‑created), the on‑disk directory name must be that folder’s stable `id` (not its display name). This ensures stable paths under version control.

## Element and File Naming

- Each element/view/relationship is stored as a single XML file in the appropriate folder.
- File name format: `<EClassSimpleName>_<id>.xml`
  - Examples: `BusinessActor_1234.xml`, `ArchimateDiagramModel_abcd.xml`
  - `<EClassSimpleName>` is the EMF simple class name of the object (e.g., `BusinessActor`, `ApplicationComponent`, `Device`, `Requirement`, `Assessment`, `ArchimateDiagramModel`, `SketchModel`, etc.). Use the exact case.
  - `<id>` is the object’s globally unique identifier string as stored in the object’s `id` attribute. The filename id and the XML `id` must match exactly.

## XML Serialization Rules (critical)

All Grafico XML files are standard EMF XML serializations of Archi objects with these constraints:

- Encoding: UTF‑8 (no BOM)
- Line endings: `\n` (UNIX newlines)
- No XML declaration at top (the exporter disables the header)
- Readable formatting is typical but not required
- Do not use the encoded attribute style (exporter disables it)

Required attributes and identity:
- Every serialized object must have an `id` attribute. It must be unique within the model and stable across commits.
- `name` attributes are optional but commonly present. The project name is read from `model/folder.xml` by scanning for `name="..."`.

Cross‑file references (must be EMF href URIs):
- References between objects are serialized as EMF `href` values pointing to other files with a fragment identifier of the target object’s `id`.
- The general form is: `<RelativeFileName>.xml#<id>` (relative to the referencing file’s location). Examples:
  - Relationship endpoints: the relationship’s `source` and `target` features reference element objects (by id) located in other files; the EMF serialization will use an href to the element file with `#<id>`.
  - Diagram objects: `IDiagramModelArchimateObject.archimateElement` references an element object by href.
  - Diagram connections: `IDiagramModelArchimateConnection.archimateRelationship` references a relationship object by href.
  - Diagram references: `IDiagramModelReference.referencedModel` references another diagram/model by href.
- Paths in hrefs must be relative (not absolute). The exporter deliberately sets resource URIs so that hrefs remain relative.
 - Use just the filename in hrefs (no folder segments). The exporter maps all non-folder resources to logical names equal to their filenames, so cross-references like `Goal_<id>.xml#<id>` resolve regardless of the containing folder.

Folders and model root:
- `model/folder.xml` serializes the root `IArchimateModel` (contains at least `id` and typically `name`).
- Each folder’s `folder.xml` serializes an `IFolder` object (contains at least `id`, `name`, and implicitly its `type` by virtue of the folder’s location/name; the serialized object itself also carries type). The importer requires that the containing folder is a directory and that `folder.xml` exists.

Profiles:
- Model profiles (`IProfile`) may be present; they are loaded and tracked by `id`. If you include profiles, ensure they have stable `id` and valid references.

Images
- Any object implementing `IDiagramModelImageProvider` may have an `imagePath` attribute. When set, the PNG/JPEG file must exist under the repository root using that path.
- Conventionally, store these under the `images/` folder and set `imagePath` to a relative path such as `images/<name-or-id>.png`.

Security and parsing:
- Do not include DTDs or external entities. The loader disables DTDs and external entity resolution for security.

## Parameters and Allowed Values

- `top_level_folders` (required): the exact set of folder names under `model/`
  - Values: `Strategy`, `Business`, `Application`, `Technology`, `Motivation`, `Implementation_Migration`, `Other`, `Relations`, `Diagrams`

- `folder_xml_presence` (required): ensure every folder dir contains `folder.xml`
  - Values: `required`

- `element_filename_pattern` (required): `<EClassSimpleName>_<id>.xml`
  - Values: `<EClassSimpleName>` = Archi EMF simple class names; `<id>` = stable identifier string

- `encoding` (required): `UTF-8`

- `line_endings` (required): `\n`

- `xml_declaration` (required): `absent`

- `href_style` (required): `relative`
  - Values: `relative` only; absolute paths are not allowed

- `image_path_base` (optional): `images/`
  - Values: relative path under repo root (recommended `images/`)

- `git_remote_name` (informational, used by tooling): `origin`

- `default_branch` (informational): `master`

- `ssh_vs_http_repo_url` (informational): if the URL is SSH (e.g., `ssh://`, `git@host:`), SSH auth paths are used by tooling; otherwise HTTP(S)

## Minimal Viable Files

At minimum, a loadable (empty) Grafico project requires:
1. `model/folder.xml` serializing an `IArchimateModel` with a valid `id` (and preferably `name`).
2. The nine top‑level subfolders under `model/`, each containing a `folder.xml` serializing an empty `IFolder` with `id` and `name` consistent with its purpose.

To add content:
- Place element/relationship/view XML files under the appropriate folder. Ensure each file’s internal `id` matches the filename’s `<id>` portion.
- For any cross‑references in those files, use relative EMF hrefs to the target file with `#<id>`.
- If any object references an image, save the image under `images/` and set the object’s `imagePath` accordingly.

## Validation Checklist

Use this checklist to avoid malformed projects:
- `model/folder.xml` exists and contains a serialized `IArchimateModel` with `id` (and `name`).
- All nine top‑level subfolders exist under `model/` and each contains a `folder.xml`.
- All files use UTF‑8, `\n` newlines, and omit XML declarations.
- Every object has a unique, stable `id`.
- All filenames follow `<EClassSimpleName>_<id>.xml` and the `<id>` matches the object’s `id` in the file.
- All cross‑references are relative hrefs ending with `#<id>` and point to existing files/ids.
- Any `imagePath` value points to an existing file under `images/`.

## Recommendations (to avoid hallucination)

- Prefer generating content via Archi’s EMF model APIs or by exporting from a valid Archi model, rather than hand‑writing XML.
- When programmatic generation is not possible, strictly follow the file/folder and href rules above. Do not invent attributes beyond those implied by the EMF features (`id`, `name`, references like `source`, `target`, `archimateElement`, `archimateRelationship`, `referencedModel`, and `imagePath`).
- Keep `id` values stable across renames/moves to preserve reference integrity and clean diffs.

## Type Catalog

Include a machine‑readable catalog of Archi types in your model repository at `types/catalog.json`. If you maintain the Archi EMF model sources (`com.archimatetool.model`) alongside your repo or in your toolchain, regenerate this catalog from those sources when upgrading Archi. Otherwise, treat the catalog as authoritative for your repo’s allowed classes.

- Fields per entry:
  - `class`: EMF implementation simple class name used in Grafico filenames
  - `kind`: `element` | `relationship` | `diagram`
  - `defaultFolder`: Recommended top-level folder under `model/` per Archi’s `getDefaultFolderForObject()` rules

Keep the catalog in sync with your Archi model version when upgrading.

## Drop‑in Usage

- Copy this `AGENTS.md` and the `types/` folder (containing `catalog.json`) into any Grafico model repository. No other files from any particular project are required.
- Tools or LLMs should rely only on:
  - The structure and serialization rules in this guide
  - The classes and folders declared in `types/catalog.json`
  - The examples and templates herein


## Namespaces and Element Names

- Declare these namespaces at the root element of every Grafico XML file:
  - `xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"`
  - `xmlns:archimate="http://www.archimatetool.com/archimate"`
- Root element name:
  - Usually the EMF simple class name with the `archimate:` prefix, e.g., `archimate:AssociationRelationship`, `archimate:Goal`, `archimate:ArchimateDiagramModel`.
  - Special cases with EMF ExtendedMetaData custom element names:
    - `IArchimateModel` serializes as `archimate:model` (not `archimate:ArchimateModel`).
    - `DiagramModelArchimateObject` serializes as `archimate:DiagramObject`.
    - `DiagramModelArchimateConnection` serializes as `archimate:Connection`.

## Relationship File Template (authoritative)

- Folder: `model/Relations/`
- Filename: `<RelationshipClass>_<id>.xml` (e.g., `AssociationRelationship_id-xxxx.xml`)

Required content
- Root element: `archimate:<RelationshipClass>`
- Attributes: `id` with a stable identifier (recommended format `id-<32-hex>`)
- Children: a `source` and a `target` element each with:
  - `xsi:type` set to the referenced element’s class (e.g., `archimate:Goal`)
  - `href` pointing to the element’s file and id: `<ElementClass>_<id>.xml#<id>`

Canonical example
<archimate:AssociationRelationship
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:archimate="http://www.archimatetool.com/archimate"
    id="id-aa2b6c09a94b4f469ef6d0287e3741ee">
  <source
      xsi:type="archimate:Goal"
      href="Goal_id-ba9ba74069e24a76876fbf50892a49b2.xml#id-ba9ba74069e24a76876fbf50892a49b2"/>
  <target
      xsi:type="archimate:Stakeholder"
      href="Stakeholder_id-081b74947cb94de6a02ce53ec65a1a0f.xml#id-081b74947cb94de6a02ce53ec65a1a0f"/>
</archimate:AssociationRelationship>

Notes
- The `xsi:type` prefix is always `archimate:` and the type name is the element class from the catalog.
- The `href` is relative to the current file’s folder. If the elements reside in other top-level folders (e.g., `model/Motivation`), EMF still writes a relative path; keep your structure consistent so relative paths resolve.

## Element File Template (minimal)

- Folder: as per `defaultFolder` from the catalog (e.g., `model/Motivation/` for `Goal`).
- Filename: `<Class>_<id>.xml`

Minimal content
<archimate:Goal
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:archimate="http://www.archimatetool.com/archimate"
    id="id-ba9ba74069e24a76876fbf50892a49b2"
    name="Example Goal"/>

## Diagram File Template

- Folder: `model/Diagrams/`
- Filename: `ArchimateDiagramModel_<id>.xml` (or `SketchModel_<id>.xml` for Sketch views)

Required structure
- Root element: `archimate:ArchimateDiagramModel` with at least `id` and `name` (optional `viewpoint`).
- Child nodes are contained under repeated `children` elements with `xsi:type="archimate:DiagramModelArchimateObject"`:
  - Attributes: `id` (unique within the model), optional `targetConnections` listing inbound connection ids (space-separated if multiple).
  - Children:
    - `bounds` element with `x`, `y`, `width`, `height` integers (use `-1` for auto width/height if desired).
    - `archimateElement` referencing the underlying element via `href` and `xsi:type` set to the element’s class.
- Connections are either contained under a node’s `sourceConnections` element with `xsi:type="archimate:DiagramModelArchimateConnection"` or referenced via `targetConnections`:
  - Attributes: `id`, `source` (diagram object id), `target` (diagram object id).
  - Child: `archimateRelationship` referencing the relationship via `href` and `xsi:type` set to the relationship’s class.

Canonical example
<archimate:ArchimateDiagramModel
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:archimate="http://www.archimatetool.com/archimate"
    name="New ArchiMate View"
    id="id-a2955814bd1b4a8daae4ec185a97ed98">
  <children
      xsi:type="archimate:DiagramModelArchimateObject"
      id="id-420e09f1a1d7454ba15e6344ad318ab5"
      targetConnections="id-8d3e2a625a354ceab94e4239bd3530b7">
    <bounds
        x="216"
        y="216"
        width="120"
        height="55"/>
    <archimateElement
        xsi:type="archimate:Stakeholder"
        href="Stakeholder_id-081b74947cb94de6a02ce53ec65a1a0f.xml#id-081b74947cb94de6a02ce53ec65a1a0f"/>
  </children>
  <children
      xsi:type="archimate:DiagramModelArchimateObject"
      id="id-4fcc996048984f29897622377bba4e85">
    <sourceConnections
        xsi:type="archimate:DiagramModelArchimateConnection"
        id="id-8d3e2a625a354ceab94e4239bd3530b7"
        source="id-4fcc996048984f29897622377bba4e85"
        target="id-420e09f1a1d7454ba15e6344ad318ab5">
      <archimateRelationship
          xsi:type="archimate:AssociationRelationship"
          href="AssociationRelationship_id-aa2b6c09a94b4f469ef6d0287e3741ee.xml#id-aa2b6c09a94b4f469ef6d0287e3741ee"/>
    </sourceConnections>
    <bounds
        x="480"
        y="204"
        width="120"
        height="55"/>
    <archimateElement
        xsi:type="archimate:Goal"
        href="Goal_id-ba9ba74069e24a76876fbf50892a49b2.xml#id-ba9ba74069e24a76876fbf50892a49b2"/>
  </children>
</archimate:ArchimateDiagramModel>

Key rules
- The `source`/`target` attributes on `DiagramModelArchimateConnection` refer to the diagram object ids (from `children id`), not the underlying element ids.
- The `archimateElement`/`archimateRelationship` children always use EMF `href` to point to the element/relationship files and ids.
- Additional optional visual attributes exist (font, colors, gradient, etc.), but you can omit them for minimal diagrams.

Allowed diagram child types (xsi:type under `children`)
- `archimate:DiagramModelArchimateObject` — wraps an ArchiMate element (shown above)
- `archimate:DiagramModelNote` — note with optional image
  - Minimal: `<children xsi:type="archimate:DiagramModelNote" id="..."><bounds x=".." y=".." width=".." height=".."/><content>Your text</content></children>`
  - Optional attributes: `textPosition` (int), `imagePath` (string), `imagePosition` (int), `borderType` (int)
- `archimate:DiagramModelImage` — image placed on the canvas
  - Minimal: `<children xsi:type="archimate:DiagramModelImage" id="..."><bounds .../><imagePath>images/my.png</imagePath></children>`
  - Optional: `borderColor` (string), `documentation`, `property`
- `archimate:DiagramModelGroup` — container of other diagram objects
  - Minimal: `<children xsi:type="archimate:DiagramModelGroup" id="..."><bounds .../></children>` then nest more `children` inside it
  - Optional: `textPosition` (int), `imagePath`, `imagePosition`, `borderType`
- `archimate:DiagramModelReference` — references another diagram
  - Minimal: `<children xsi:type="archimate:DiagramModelReference" id="..."><bounds .../><referencedModel href="ArchimateDiagramModel_<id>.xml#<id>"/></children>`

## Object Properties Reference

This section lists the important, non‑guessable properties available on objects. When in doubt, omit optional properties — Archi provides defaults.

- Common to all concepts (elements and relationships)
  - `id` (string, required): stable unique identifier
  - `name` (string, optional)
  - `documentation` (element, optional): serialized as `<documentation>free text</documentation>`
  - `property` (repeatable element, optional): `<property key="..." value="..."/>`
  - `profile` references (optional): advanced; omit unless using profiles

- Model root (`archimate:model` in `model/folder.xml`)
  - Attributes: `id` (required), `name` (optional), `version` (optional)
  - Children: `purpose` (element, optional), `metadata` (optional), `profile` entries (optional)

- Folder (`archimate:Folder` in each `folder.xml`)
  - Attributes: `id` (required), `name` (required), `type` (required)
  - `type` allowed values: `STRATEGY`, `BUSINESS`, `APPLICATION`, `TECHNOLOGY`, `MOTIVATION`, `IMPLEMENTATION_MIGRATION`, `OTHER`, `RELATIONS`, `DIAGRAMS`, `USER`

- ArchiMate Element files (e.g., `archimate:Goal`)
  - Attributes: `id` (required), `name` (optional)
  - Children: `documentation` (optional), `property` (0..*)

- ArchiMate Relationship files (e.g., `archimate:AssociationRelationship`)
  - Attributes: `id` (required), `name` (optional)
  - Children: `documentation` (optional), `property` (0..*), and the required ends:
    - `source` (required): `xsi:type` set to element type; `href` points to the source element file and id
    - `target` (required): `xsi:type` set to element type; `href` points to the target element file and id

- Diagram model (`archimate:ArchimateDiagramModel` or `archimate:SketchModel`)
  - Attributes: `id` (required), `name` (optional), `viewpoint` (optional string)
  - Children: `children` (0..*), `documentation` (optional), `property` (0..*)

- Diagram object (`xsi:type="archimate:DiagramModelArchimateObject"` under `children`)
  - Attributes (common): `id` (required)
  - Children (required):
    - `bounds` with attributes `x`, `y`, `width`, `height` (integers)
    - `archimateElement` with `xsi:type` and `href` pointing to the element
  - Optional attributes (visual style): `fillColor` (string), `alpha` (int 0–255), `lineWidth` (int), `lineColor` (string), `textAlignment` (int)
  - Optional features (serialized as `<feature name="..." value="..."/>`):
    - `lineAlpha` (int, default 255)
    - `gradient` (int, default 0 = none)
    - `iconVisible` (int; default shows icon if no image)
    - `iconColor` (string)
    - `deriveElementLineColor` (boolean, default true)
    - `lineStyle` (int; default solid)
    - For archimate objects specifically: `imageSource` (int; default uses profile image)

- Diagram connection (`xsi:type="archimate:DiagramModelArchimateConnection"` under `sourceConnections`)
  - Attributes: `id` (required), `source` (diagram object id), `target` (diagram object id)
  - Children: `archimateRelationship` with `xsi:type` and `href` to relationship file/id
  - Optional children: bendpoints
    - Each bendpoint is serialized as a `<bendpoints xsi:type="archimate:DiagramModelBendpoint" startX=".." startY=".." endX=".." endY=".."/>` element
  - Optional attributes (visual): `lineWidth`, `lineColor`, `text`, `textPosition` (int)
  - Optional feature: `nameVisible` (boolean) via `<feature name="nameVisible" value="true|false"/>`

Notes on features vs attributes
- Visual/styling settings appear either as direct attributes (e.g., `fillColor`) or as `feature` elements with a `name` and `value`. Names are exactly as listed above.
- All visual features are optional; omit them for minimal, valid diagrams.

## folder.xml Templates

- Model root: `model/folder.xml`
  - Root element is `archimate:model` and includes at least `id` and optionally `name`, `version`, `purpose`.
  - Minimal example:
    <archimate:model
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xmlns:archimate="http://www.archimatetool.com/archimate"
        id="id-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        name="My Model"/>

- Folder root: each folder’s `folder.xml`
  - Root element is `archimate:Folder` with at least `id`, `name`, and `type` consistent with its placement.
  - Minimal example:
    <archimate:Folder
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xmlns:archimate="http://www.archimatetool.com/archimate"
        id="id-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        name="Business"
        type="BUSINESS"/>

## Notes

- The importer is tolerant in some areas (e.g., it scans for `name="..."` in `model/folder.xml` to derive a repository display name if the model is not open), but do not rely on this leniency for correctness.
- This guide reflects constraints enforced by:
  - `IGraficoConstants` (filenames/paths)
  - `GraficoModelExporter` (serialization and layout)
  - `GraficoModelImporter` (loading, proxy resolution, required files)
  - `GraficoResourceLoader` (XML load options and security)
