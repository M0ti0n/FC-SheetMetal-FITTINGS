# HVAC Fittings – FreeCAD workbench

Flat patterns of sheet-metal duct fittings, HACO style:
**choose fitting → enter dimensions → flat pattern in the model space → check → export DXF.**

Everything is calculated on the **neutral surface** (no sheet thickness, no K-factor).
The flat pattern is the main result; the generated sketches can optionally be used
in the SheetMetal workbench for a 3D check.

## Status (v0.1)

| Fitting | Status |
|---|---|
| Round segmented elbow | ✅ working |
| Rectangular → round eccentric transition | ✅ working |
| Round reducer with branch | planned |
| Simple reducer | planned |

## Install

Copy (or `git clone`) this folder into your FreeCAD `Mod` directory and restart FreeCAD:

| OS | Mod folder (FreeCAD 1.0) |
|---|---|
| Windows | `%APPDATA%\FreeCAD\Mod\` (0.21: `%APPDATA%\FreeCAD\Mod\`) |
| Linux | `~/.local/share/FreeCAD/Mod/` |
| macOS | `~/Library/Application Support/FreeCAD/Mod/` |

Tip: in FreeCAD's Python console, `App.getUserAppDataDir()` prints the folder that contains `Mod`.
Then pick **HVAC Fittings** in the workbench selector. No extra Python packages are needed.

## Segmented elbow

Parameters (see the diagram in the task panel):

| | |
|---|---|
| **D** | diameter (neutral) |
| **A** | elbow angle |
| **R** | centreline radius |
| **N** | number of **full middle sections**; the 2 end sections (**B**) are added automatically |

Convention: every end section is exactly half of a middle section, cut perpendicular to the
duct axis, so one middle section spans `A / (N + 1)`.
Example: A = 90°, N = 3 → ½ + 3 + ½ pieces, 22.5° per middle section.

Development (x around the circumference, y along the axis):
`h(φ) = (R + D/2·cos φ) · tan(θ/2)`, θ = A/(N+1), φ = 0 at the heel.
Middle section: `−h … +h`. End section: `0 … +h`. Developed length `π·D`.

### Tree

```
Elbow D400 A90 R800 N3        <- all parameters (also editable in the property editor)
├─ Middle Section x3
│  ├─ Middle_Cut              <- Sketch: closed cutting contour
│  ├─ Middle_Folds            <- Sketch: folding lines
│  └─ Middle_Annotations      <- reference lines, dimensions, labels
└─ End Section x2
   ├─ End_Cut
   ├─ End_Folds
   └─ End_Annotations
```

Defaults: **Add reference dimensions**, **Add folding labels** and **Add annotations** are off, so a
fresh pattern (and its DXF) contains only the cut contour and the fold marks. *Add annotations*
(Preview Options) adds the heel / side / throat and mid-plane reference lines plus the piece name,
quantity and parameters.

Double-click the elbow to reopen the task panel. *Preview Options* only toggles what is shown;
the model space shows the flat patterns only.

### DXF (R12, layers)

| Layer | Content |
|---|---|
| CUT | cutting contour: one closed polyline of lines + arcs (arcs as bulges, max 0.01 mm from the true curve) |
| FOLD | press-brake fold marks: two 15 mm lines per fold, starting 2 mm inside each cut edge |
| REF | heel / side / throat and mid-plane reference lines |
| DIM | reference dimensions (as lines) |
| TEXT | piece name, quantity, parameters, fold labels |

*Export DXF* writes exactly what is visible, read from the actual sketches – so moving or
editing a sketch by hand is reflected in the export.

**No splines anywhere.** The cut curves are fitted with circular arcs (≤ 0.01 mm deviation), both in the
sketches and in the DXF, so even FreeCAD's own *File → Export* produces arcs, not splines.

Fold marks: **FoldMarkLength** (15 mm) and **FoldMarkGap** (2 mm from the edge) are in the property editor.
If a piece is too short for two separate marks, they merge into one line (gaps kept).

Extra property (property editor only): **SeamPosition** = Side (default, mid-length seam) / Throat / Heel.

## Rectangular → round transition

Parameters (see the diagram in the task panel):

| | |
|---|---|
| **A, B** | AB side: rectangle edge left / right of the round centre (side length A + B) |
| **E, F** | EF side: rectangle edge above / below the round centre (side length E + F) |
| **D** | diameter of the round end (neutral) |
| **H** | height between the rectangular and the round end |
| **N** | sections per quarter of the round → 4 × (N + 1) fold lines |

Development by triangulation: each rectangle corner fans out to its quarter of the round
(oblique cone), each rectangle side is one flat triangle. The round edge is developed exactly
(length π·D) and written as arcs; every developed length equals its 3D length.

**Seam:** on the longer rectangle side (AB side if A + B ≥ E + F, otherwise EF side), running from
the round straight down to that side – on an AB side it splits the side into A and B, on an EF side
into E and F. Of the two parallel long sides the one farther from the round centre is used;
*SeamSide* in the property editor overrides this.

**Fold marks** are drawn only at the round edge (15 mm, 2 mm in): all fold lines of a fan meet in the
rectangle corner, so marks there would sit on top of each other.

Preview Options: *Show flat pattern*, **Pattern** and *Add annotations* (triangulation lines + piece label).

| Pattern | Pieces |
|---|---|
| **Combined** | whole fitting in one piece, seam on the longer side |
| **Short Side** | each short-side triangle with the corner parts bent on both sides of it (half of the round) |
| **Long Side** | each long-side triangle, flat, no round parts |

Short Side + Long Side together make the whole fitting (4 pieces, joined along the long-side
triangle edges; the joint lengths match exactly). Because the rectangle can be off-centre, the two
short (or long) pieces differ; when the rectangle is centred across them they are the same part and
are generated once as ×2. Each piece is laid with its rectangle edge on the x axis.
If the pattern would overlap itself (very low H), a warning is shown.

### SheetMetal (optional 3D check)

`*_Cut` is a closed sketch usable as a SheetMetal base shape; `*_Folds` holds the fold lines
for *Fold on line*.

## Layout

```
InitGui.py / Init.py          workbench registration
hvacdev/geometry/             pure-Python development math, arc fitting, sheet layout (no FreeCAD)
hvacdev/dxf/                  dependency-free DXF R12 writer
hvacdev/freecad/              feature objects, task panel, commands, export
resources/                    icons, task-panel diagrams
tools/make_elbow_diagram.py   regenerates resources/diagrams/elbow.svg
tests/                        `python tests/test_elbow.py`, `python tests/test_transition.py` (no FreeCAD needed)
```
