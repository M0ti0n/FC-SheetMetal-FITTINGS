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
| Round reducer with branch | ✅ working |
| Simple reducer | planned |
| Flange (slots) | ✅ working |
| Threaded flange (drill & tap marks) | ✅ working |

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
| MARK | scribe / punch marks (threaded-flange drill crosses) |

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

Preview Options: *Show flat pattern* with the tick boxes **Combined**, **Short Side** and **Long Side**
(any combination; each ticked pattern gets its own row in the model space and in the DXF), and
*Add annotations* (triangulation lines + piece label).

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

## Branch reducer (round reducer with branch)

Parameters (see the diagram in the task panel):

| | |
|---|---|
| **D1 / D2** | reducer diameter at the top / bottom (neutral) |
| **H1** | reducer height |
| **H2** | height where the branch axis meets the reducer side |
| **D3** | branch diameter (neutral) |
| **L** | from that point along the branch axis to the (square) branch end |
| **A** | branch angle above the horizontal |

Two pieces: **Reducer** (cone development, or a rectangle when D1 = D2) and **Branch** (pipe
development). The branch hole and the branch's fitted edge are calculated from the exact
intersection of the two surfaces, so both have the true 3D length and the branch fits the hole.

**Seams:** the reducer seam runs along the reducer straight through the middle of the branch hole,
so the hole appears as two half-holes, one on each seam edge. The branch seam is on its shortest
generator – the top one in the usual case (it moves to the bottom when the reducer shape makes the
bottom generator shorter, e.g. a horizontal branch on a reducer narrowing upwards).

Preview Options: *Show flat pattern* with **Reducer** and **Branch** tick boxes, *Add annotations*.
The same fold-line count is used around the reducer and around the branch; fold marks never fall
inside the hole.

## Flange

Flat ring flange with arc slots.

| | |
|---|---|
| **A** | inner (nominal) diameter |
| **B** | diameter the slots lie on |
| **M** | slot width; slots are always **25 mm** between the end-hole centres |
| **N** | number of slots, equally spaced, the first one at the top |
| **E** | ring width – outer diameter **D = A + 2E** |
| **T** | recommended thickness (information only) |

*Diameter (A)* is an editable list of the 44 standard sizes (A80 … A820, from
`parameters_flange_tool.ods`, stored in `hvacdev/geometry/flange_table.py`). Picking a size fills in
B, M, N, E and T; any other A can be typed – the values of the nearest smaller standard size are
then used (same B – A offset). Every value can still be changed by hand. The tool checks that the
slots stay inside the ring and do not touch each other.

**D** and **T** are only written when *Add reference dimensions* or *Add annotations* is on.
Circles and slots are arcs only (each circle = 2 arcs, each slot = 4 arcs).

### Divided flange (both flange tools)

Preview Options has **Combined** (the whole flange) and **Divided** (the flange cut into 3 sections);
both can be ticked, each gets its own row.

* Every cut is radial and lies exactly midway between two slots / cross marks – never through one.
* **N divisible by 3** (3, 6, 9, 12 …): three equal 120° sections → one drawing **×3**.
* **Otherwise** the holes are split as evenly as possible: two identical sections **A ×2** and one
  different section **B ×1**, e.g. N 8 → A 3 slots 135° ×2 + B 2 slots 90°; N 10 → A 3 slots 108° ×2 +
  B 4 slots 144°; N 16 → A 5 × 112.5° ×2 + B 6 × 135°.
* **A80 and A100 are never divided** (Divided is greyed out).
* Each section is drawn with its middle pointing up; with annotations or reference dimensions on it
  is labelled with its name, quantity, angle and number of slots / holes.

## Threaded flange

Same ring as the flange, but instead of slots each hole position gets an **X cross mark** where the
hole is drilled and tapped after cutting. No M dimension in the diagram – **M is the thread**
(M6 / M8 / M10 …) and only used for information and the check that the holes fit.

| | |
|---|---|
| **A** | inner (nominal) diameter |
| **B** | diameter the holes lie on |
| **M** | metric thread; the tap drill is shown (M6 → 5.0, M8 → 6.8, M10 → 8.5) |
| **N** | number of holes, equally spaced, the first one at the top |
| **E** | ring width – outer diameter **D = A + 2E** |
| **T** | recommended thickness (information only) |

44 standard sizes from `parameters_flange_tool-metric_thread.ods`
(`hvacdev/geometry/flange_thread_table.py`), same size list behaviour as the flange.
Flat Pattern Options: *Add cross marks* with the mark size (default 10 mm) and *Add reference
dimensions*. In the DXF the circles are on **CUT** and the crosses on their own layer **MARK**, so
they can be scribed / punched instead of cut. D and T only appear with reference dimensions or
annotations on.

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
tests/                        `python tests/test_elbow.py`, `test_transition.py`, `test_branch_reducer.py`, `test_flange.py`, `test_flange_thread.py`, `test_flange_divide.py` (no FreeCAD needed)
```
