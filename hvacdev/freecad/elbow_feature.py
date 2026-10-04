# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parametric segmented-elbow object.

Tree structure created by make_elbow():

    Elbow D400 A90 R800 N3            <- this object, holds all parameters
    ├─ Middle Section x3              <- App::DocumentObjectGroup
    │  ├─ Middle_Cut                  <- Sketch, closed cutting contour
    │  ├─ Middle_Folds                <- Sketch, folding lines only
    │  └─ Middle_Annotations          <- reference lines, dimensions, labels
    └─ End Section x2
       ├─ End_Cut
       ├─ End_Folds
       └─ End_Annotations

The cut contour and the fold lines are separate sketches on purpose: the
closed _Cut sketch can be used directly as a SheetMetal base shape, and a
_Folds sketch is what SheetMetal "Fold on line" expects.
"""

import FreeCAD as App
import Part

from hvacdev.geometry import elbow as eg
from hvacdev.geometry import layout
from hvacdev.freecad import annotations

SECTIONS = ("Middle", "End")


def _params_from(obj):
    return eg.ElbowParams(
        diameter=float(obj.Diameter.Value),
        angle=float(obj.Angle.Value),
        radius=float(obj.Radius.Value),
        middle_sections=int(obj.MiddleSections),
        fold_lines=int(obj.FoldingLineCount) if obj.AddFoldingLines else 0,
        fold_mark_length=float(obj.FoldMarkLength.Value),
        fold_mark_gap=float(obj.FoldMarkGap.Value),
        seam=str(obj.SeamPosition),
    )


def params_text(p):
    return "D%g  A%g deg  R%g  N%d" % (p.diameter, p.angle, p.radius, p.middle_sections)


class ElbowFeature:
    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "HVAC_SegmentedElbow"
        self.add_properties(obj)

    @staticmethod
    def add_properties(obj):
        have = obj.PropertiesList

        def add(ptype, name, group, doc, value=None, mode=None):
            if name not in have:
                obj.addProperty(ptype, name, group, doc)
                if value is not None:
                    setattr(obj, name, value)
            if mode is not None:
                obj.setEditorMode(name, mode)

        g = "Main Parameters"
        add("App::PropertyLength", "Diameter", g, "D - neutral diameter", 400.0)
        add("App::PropertyAngle", "Angle", g, "A - elbow angle", 90.0)
        add("App::PropertyLength", "Radius", g, "R - centreline radius", 800.0)
        add("App::PropertyIntegerConstraint", "MiddleSections", g,
            "N - number of full middle sections (end sections are added automatically)",
            (3, 0, 99, 1))

        g = "Manufacturing Options"
        add("App::PropertyBool", "AddFoldingLines", g, "Add press-brake folding lines", True)
        add("App::PropertyIntegerConstraint", "FoldingLineCount", g,
            "Number of folding lines around the circumference", (24, 1, 720, 1))
        add("App::PropertyLength", "FoldMarkLength", g, "Length of each fold mark", 15.0)
        add("App::PropertyLength", "FoldMarkGap", g, "Distance of the fold mark from the cut edge", 2.0)
        add("App::PropertyBool", "AddReferenceDimensions", g, "Add reference dimensions", False)
        add("App::PropertyBool", "AddFoldingLabels", g, "Label the folding lines", False)
        if "SeamPosition" not in have:
            obj.addProperty("App::PropertyEnumeration", "SeamPosition", g,
                            "Where the longitudinal seam of the pattern lies")
            obj.SeamPosition = list(eg.SEAM_POSITIONS)
            obj.SeamPosition = eg.SEAM_SIDE

        g = "Preview Options"
        add("App::PropertyBool", "ShowFlatPattern", g, "Show flat patterns in the model space", True)
        add("App::PropertyBool", "ShowMiddle", g, "Show the middle section (N)", True)
        add("App::PropertyBool", "ShowEnd", g, "Show the end section (B)", True)
        add("App::PropertyBool", "AddAnnotations", g,
            "Reference lines (heel / side / throat, mid-plane) and piece name / quantity", False)

        g = "Result"
        add("App::PropertyAngle", "SegmentAngle", g, "Angle of one middle section", mode=1)
        add("App::PropertyLength", "DevelopedLength", g, "Developed length = pi * D", mode=1)

        g = "Internal"
        for s in SECTIONS:
            for part in ("Group", "Cut", "Folds", "Annotations"):
                add("App::PropertyLink", s + part, g, "", mode=2)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def children(obj, section):
        return [getattr(obj, section + p, None) for p in ("Cut", "Folds", "Annotations")]

    def execute(self, obj):
        p = _params_from(obj)
        errors = p.validate()
        if errors:
            raise ValueError("\n".join(errors))
        regenerate(obj, p)

    def onChanged(self, obj, prop):
        if "Restore" in getattr(obj, "State", []):
            return
        if prop in ("ShowFlatPattern", "ShowMiddle", "ShowEnd", "AddFoldingLines"):
            apply_visibility(obj)

    def onDocumentRestored(self, obj):
        self.add_properties(obj)

    def dumps(self):
        return {"Type": self.Type}

    def loads(self, state):
        self.Type = "HVAC_SegmentedElbow"

    __getstate__ = dumps
    __setstate__ = loads


# ---------------------------------------------------------------------------
# geometry -> FreeCAD objects
# ---------------------------------------------------------------------------
def _line(a, b):
    return Part.LineSegment(App.Vector(a[0], a[1], 0), App.Vector(b[0], b[1], 0))


def _seg_geometry(sg):
    """arcs.Seg -> sketch geometry. Only lines and circular arcs, never splines."""
    V = App.Vector
    if sg.is_arc:
        return Part.ArcOfCircle(V(sg.start[0], sg.start[1], 0), V(sg.mid[0], sg.mid[1], 0),
                                V(sg.end[0], sg.end[1], 0))
    return _line(sg.start, sg.end)


def _cut_geometry(section):
    """Closed cutting contour: straight seam edges + chains of arcs."""
    return [_seg_geometry(sg) for sg in section.contour]


def _set_sketch(sk, geometry, placement):
    sk.deleteAllGeometry()
    if geometry:
        sk.addGeometry(geometry, False)
    sk.Placement = placement
    sk.recompute()


def regenerate(obj, p=None):
    p = p or _params_from(obj)
    middle, end = eg.develop(p)
    opts = layout.Options(
        fold_lines=obj.AddFoldingLines,
        reference_dims=obj.AddReferenceDimensions,
        fold_labels=obj.AddFoldingLabels and obj.AddFoldingLines,
        reference_lines=obj.AddAnnotations,
        piece_labels=obj.AddAnnotations,
    )
    ptxt = params_text(p)
    offs = layout.offsets(middle, end, p.diameter)
    sections = {"Middle": (middle, "middle"), "End": (end, "end")}

    for name, (sec, key) in sections.items():
        grp = getattr(obj, name + "Group", None)
        cut, folds, anno = ElbowFeature.children(obj, name)
        placed = layout.place(sec, key, (0.0, 0.0), opts, ptxt, p.diameter)
        pl = App.Placement(App.Vector(offs[key][0], offs[key][1], 0), App.Rotation())
        if grp:
            grp.Label = "%s x%d" % (sec.name, sec.quantity)
        if cut:
            _set_sketch(cut, _cut_geometry(sec), pl)
        if folds:
            _set_sketch(folds, [_line(a, b) for a, b in placed.fold], pl)
        if anno:
            anno.Placement = pl
            anno.Proxy.set_data(anno, placed.ref, placed.dim, placed.text)

    obj.SegmentAngle = eg.segment_angle(p)
    obj.DevelopedLength = middle.width
    apply_visibility(obj)


def apply_visibility(obj):
    if not App.GuiUp:
        return
    needed = ("ShowFlatPattern", "ShowMiddle", "ShowEnd", "MiddleSections",
              "AddFoldingLines", "EndAnnotations")
    if any(n not in obj.PropertiesList for n in needed):
        return  # still being constructed
    show = obj.ShowFlatPattern
    flags = {"Middle": show and obj.ShowMiddle and obj.MiddleSections > 0,
             "End": show and obj.ShowEnd}
    for name, vis in flags.items():
        grp = getattr(obj, name + "Group", None)
        if grp and grp.ViewObject:
            grp.ViewObject.Visibility = vis
        cut, folds, anno = ElbowFeature.children(obj, name)
        has_anno = bool(anno and (anno.RefLines or anno.DimLines or anno.Texts))
        for child, extra in ((cut, True), (folds, obj.AddFoldingLines), (anno, has_anno)):
            if child and child.ViewObject:
                child.ViewObject.Visibility = vis and extra


# ---------------------------------------------------------------------------
# view provider
# ---------------------------------------------------------------------------
class ViewProviderElbow:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        from hvacdev.freecad import resources
        return resources.icon("SegmentedElbow.svg")

    def claimChildren(self):
        obj = self.Object
        return [g for g in (getattr(obj, "MiddleGroup", None), getattr(obj, "EndGroup", None)) if g]

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        import FreeCADGui as Gui
        from hvacdev.freecad.elbow_taskpanel import ElbowTaskPanel
        Gui.Control.showDialog(ElbowTaskPanel(vobj.Object, is_new=False))
        return True

    def unsetEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        import FreeCADGui as Gui
        if Gui.Control.activeDialog():
            Gui.Control.closeDialog()
        return True

    def doubleClicked(self, vobj):
        import FreeCADGui as Gui
        Gui.ActiveDocument.setEdit(vobj.Object, 0)
        return True

    def setupContextMenu(self, vobj, menu):
        from PySide import QtGui
        act = QtGui.QAction("Edit elbow", menu)
        act.triggered.connect(lambda: self.doubleClicked(vobj))
        menu.addAction(act)

    def onDelete(self, vobj, subelements):
        delete_children(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def delete_children(obj):
    doc = obj.Document
    names = []
    for s in SECTIONS:
        for part in ("Cut", "Folds", "Annotations", "Group"):
            child = getattr(obj, s + part, None)
            if child:
                names.append(child.Name)
                setattr(obj, s + part, None)
    for n in names:
        if doc.getObject(n):
            doc.removeObject(n)


# ---------------------------------------------------------------------------
# factory
# ---------------------------------------------------------------------------
def make_elbow(doc=None, **values):
    doc = doc or App.ActiveDocument or App.newDocument()
    obj = doc.addObject("App::FeaturePython", "Elbow")
    ElbowFeature(obj)
    for k, v in values.items():
        setattr(obj, k, v)

    for name in SECTIONS:
        grp = doc.addObject("App::DocumentObjectGroup", name + "Section")
        cut = doc.addObject("Sketcher::SketchObject", name + "_Cut")
        folds = doc.addObject("Sketcher::SketchObject", name + "_Folds")
        anno = annotations.make(doc, name + "_Annotations", name + "_Annotations")
        for child in (cut, folds, anno):
            grp.addObject(child)
        setattr(obj, name + "Group", grp)
        setattr(obj, name + "Cut", cut)
        setattr(obj, name + "Folds", folds)
        setattr(obj, name + "Annotations", anno)
        if App.GuiUp:
            folds.ViewObject.LineColor = (0.85, 0.1, 0.1)
            for prop, val in (("LineWidth", 1.5),):
                try:
                    setattr(folds.ViewObject, prop, val)
                except Exception:
                    pass
            cut.ViewObject.LineWidth = 2.0

    if App.GuiUp:
        ViewProviderElbow(obj.ViewObject)
    update_label(obj)
    return obj


def update_label(obj):
    obj.Label = "Elbow D%g A%g R%g N%d" % (obj.Diameter.Value, obj.Angle.Value,
                                          obj.Radius.Value, obj.MiddleSections)
