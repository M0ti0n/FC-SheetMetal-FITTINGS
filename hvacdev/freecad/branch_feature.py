# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parametric reducer with branch.

Tree:
    Branch reducer D1 200 D2 400 H1 400 ...
    ├─ Reducer x1                 <- group
    │  ├─ Reducer_Cut             <- Sketch: closed contour incl. the two half-holes
    │  ├─ Reducer_Folds           <- Sketch: fold marks
    │  └─ Reducer_Annotations
    └─ Branch x1
       ├─ Branch_Cut
       ├─ Branch_Folds
       └─ Branch_Annotations
"""

import FreeCAD as App

from hvacdev.geometry import branch_reducer as bg
from hvacdev.geometry import branch_layout
from hvacdev.geometry import layout
from hvacdev.freecad import annotations
from hvacdev.freecad.elbow_feature import _line, _seg_geometry, _set_sketch

SECTIONS = ("Reducer", "Branch")
PARTS = ("Group", "Cut", "Folds", "Annotations")


def params_from(obj):
    return bg.BranchReducerParams(
        d1=float(obj.DiameterTop.Value), d2=float(obj.DiameterBottom.Value),
        h1=float(obj.Height.Value), h2=float(obj.BranchHeight.Value),
        d3=float(obj.BranchDiameter.Value), length=float(obj.BranchLength.Value),
        angle=float(obj.BranchAngle.Value),
        fold_lines=int(obj.FoldingLineCount) if obj.AddFoldingLines else 0,
        fold_mark_length=float(obj.FoldMarkLength.Value),
        fold_mark_gap=float(obj.FoldMarkGap.Value),
    )


def params_text(p):
    return "D1 %g D2 %g H1 %g  H2 %g D3 %g L %g A %g" % (p.d1, p.d2, p.h1, p.h2, p.d3, p.length, p.angle)


class BranchReducerFeature:
    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "HVAC_BranchReducer"
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
        add("App::PropertyLength", "DiameterTop", g, "D1 - reducer diameter at the top (neutral)", 200.0)
        add("App::PropertyLength", "DiameterBottom", g, "D2 - reducer diameter at the bottom (neutral)", 400.0)
        add("App::PropertyLength", "Height", g, "H1 - reducer height", 400.0)
        add("App::PropertyLength", "BranchHeight", g,
            "H2 - height where the branch axis meets the reducer side", 200.0)
        add("App::PropertyLength", "BranchDiameter", g, "D3 - branch diameter (neutral)", 160.0)
        add("App::PropertyLength", "BranchLength", g,
            "L - from the reducer side along the branch axis to the branch end", 250.0)
        add("App::PropertyAngle", "BranchAngle", g, "A - branch axis above the horizontal", 30.0)

        g = "Flat Pattern Options"
        add("App::PropertyBool", "AddFoldingLines", g, "Add press-brake fold marks", True)
        add("App::PropertyIntegerConstraint", "FoldingLineCount", g,
            "Fold lines around the reducer and around the branch", (24, 1, 720, 1))
        add("App::PropertyLength", "FoldMarkLength", g, "Length of each fold mark", 15.0)
        add("App::PropertyLength", "FoldMarkGap", g, "Distance of the fold mark from the cut edge", 2.0)
        add("App::PropertyBool", "AddReferenceDimensions", g, "Add reference dimensions", False)
        add("App::PropertyBool", "AddFoldingLabels", g, "Label the folding lines", False)

        g = "Preview Options"
        add("App::PropertyBool", "ShowFlatPattern", g, "Show flat patterns in the model space", True)
        add("App::PropertyBool", "ShowReducer", g, "Show the reducer pattern", True)
        add("App::PropertyBool", "ShowBranch", g, "Show the branch pattern", True)
        add("App::PropertyBool", "AddAnnotations", g,
            "Reference generators (side / back / top / bottom) and piece name / quantity", False)

        g = "Result"
        add("App::PropertyLength", "ReducerSeam", g, "Reducer seam length (through the branch hole)", mode=1)
        add("App::PropertyLength", "BranchSeam", g, "Branch seam length (shortest generator)", mode=1)
        add("App::PropertyString", "BranchSeamOn", g, "Where the branch seam lies", mode=1)

        g = "Internal"
        for s in SECTIONS:
            for part in PARTS:
                add("App::PropertyLink", s + part, g, "", mode=2)

    @staticmethod
    def children(obj, section):
        return [getattr(obj, section + p, None) for p in ("Cut", "Folds", "Annotations")]

    def execute(self, obj):
        p = params_from(obj)
        errors = p.validate()
        if errors:
            raise ValueError("\n".join(errors))
        regenerate(obj, p)

    def onChanged(self, obj, prop):
        if "Restore" in getattr(obj, "State", []):
            return
        if prop in ("ShowFlatPattern", "ShowReducer", "ShowBranch", "AddFoldingLines"):
            apply_visibility(obj)

    def onDocumentRestored(self, obj):
        self.add_properties(obj)

    def dumps(self):
        return {"Type": self.Type}

    def loads(self, state):
        self.Type = "HVAC_BranchReducer"

    __getstate__ = dumps
    __setstate__ = loads


def regenerate(obj, p=None):
    p = p or params_from(obj)
    reducer, branch = bg.develop(p)
    gap = max(60.0, 0.15 * p.d2)
    bg.layout(reducer, branch, gap)          # both always laid out: positions stay put when toggling
    opts = layout.Options(
        fold_lines=obj.AddFoldingLines,
        reference_dims=obj.AddReferenceDimensions,
        fold_labels=obj.AddFoldingLabels and obj.AddFoldingLines,
        reference_lines=obj.AddAnnotations,
        piece_labels=obj.AddAnnotations,
    )
    ptxt = params_text(p)
    for name, pc in (("Reducer", reducer), ("Branch", branch)):
        grp = getattr(obj, name + "Group", None)
        cut, folds, anno = BranchReducerFeature.children(obj, name)
        pl = App.Placement(App.Vector(pc.offset[0], pc.offset[1], 0), App.Rotation())
        if grp:
            grp.Label = "%s x%d" % (pc.name, pc.quantity)
        if cut:
            _set_sketch(cut, [_seg_geometry(sg) for sg in pc.contour], pl)
        if folds:
            _set_sketch(folds, [_line(a, b) for a, b in pc.fold_marks] if p.fold_lines else [], pl)
        if anno:
            ref, dim, texts = branch_layout.annotations(pc, opts, ptxt, p.d2)
            anno.Placement = pl
            anno.Proxy.set_data(anno, ref, dim, texts)
    obj.ReducerSeam = reducer.seam_length
    obj.BranchSeam = branch.seam_length
    import math
    obj.BranchSeamOn = "top" if math.cos(branch.top_beta) >= 0 else "bottom"
    apply_visibility(obj)


def apply_visibility(obj):
    if not App.GuiUp:
        return
    needed = ("ShowFlatPattern", "ShowReducer", "ShowBranch", "AddFoldingLines", "BranchAnnotations")
    if any(n not in obj.PropertiesList for n in needed):
        return
    show = obj.ShowFlatPattern
    for name, vis in (("Reducer", show and obj.ShowReducer), ("Branch", show and obj.ShowBranch)):
        grp = getattr(obj, name + "Group", None)
        if grp and grp.ViewObject:
            grp.ViewObject.Visibility = vis
        cut, folds, anno = BranchReducerFeature.children(obj, name)
        has_anno = bool(anno and (anno.RefLines or anno.DimLines or anno.Texts))
        for child, extra in ((cut, True), (folds, obj.AddFoldingLines), (anno, has_anno)):
            if child and child.ViewObject:
                child.ViewObject.Visibility = vis and extra


class ViewProviderBranchReducer:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        from hvacdev.freecad import resources
        return resources.icon("BranchReducer.svg")

    def claimChildren(self):
        obj = self.Object
        return [g for g in (getattr(obj, "ReducerGroup", None), getattr(obj, "BranchGroup", None)) if g]

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        import FreeCADGui as Gui
        from hvacdev.freecad.branch_taskpanel import BranchReducerTaskPanel
        Gui.Control.showDialog(BranchReducerTaskPanel(vobj.Object, is_new=False))
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
        act = QtGui.QAction("Edit branch reducer", menu)
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


def make_branch_reducer(doc=None, **values):
    doc = doc or App.ActiveDocument or App.newDocument()
    obj = doc.addObject("App::FeaturePython", "BranchReducer")
    BranchReducerFeature(obj)
    for k, v in values.items():
        setattr(obj, k, v)
    for name in SECTIONS:
        grp = doc.addObject("App::DocumentObjectGroup", name + "Piece")
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
            try:
                folds.ViewObject.LineWidth = 1.5
                cut.ViewObject.LineWidth = 2.0
            except Exception:
                pass
    if App.GuiUp:
        ViewProviderBranchReducer(obj.ViewObject)
    update_label(obj)
    return obj


def update_label(obj):
    obj.Label = "Branch reducer D1 %g D2 %g H1 %g H2 %g D3 %g L %g A %g" % (
        obj.DiameterTop.Value, obj.DiameterBottom.Value, obj.Height.Value, obj.BranchHeight.Value,
        obj.BranchDiameter.Value, obj.BranchLength.Value, obj.BranchAngle.Value)
