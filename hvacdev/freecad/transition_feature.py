# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parametric rectangular -> round (eccentric) transition.

Tree:
    Transition D400 H300 A300 B200 E150 F250 N4   <- parameters
    ├─ Transition_Cut           <- Sketch: closed cutting contour (lines + arcs)
    ├─ Transition_Folds         <- Sketch: fold marks
    └─ Transition_Annotations   <- triangulation lines, dimensions, labels
"""

import FreeCAD as App

from hvacdev.geometry import transition as tg
from hvacdev.geometry import transition_layout
from hvacdev.geometry import layout
from hvacdev.freecad import annotations
from hvacdev.freecad.elbow_feature import _line, _seg_geometry, _set_sketch

PARTS = ("Cut", "Folds", "Annotations")


def params_from(obj):
    return tg.TransitionParams(
        diameter=float(obj.Diameter.Value), height=float(obj.Height.Value),
        a=float(obj.SideA.Value), b=float(obj.SideB.Value),
        e=float(obj.SideE.Value), f=float(obj.SideF.Value),
        sections=int(obj.SectionsPerQuarter), seam=str(obj.SeamSide),
        fold_lines=bool(obj.AddFoldingLines),
        fold_mark_length=float(obj.FoldMarkLength.Value),
        fold_mark_gap=float(obj.FoldMarkGap.Value),
    )


def params_text(p):
    return "D%g H%g  A%g B%g  E%g F%g  N%d" % (p.diameter, p.height, p.a, p.b, p.e, p.f, p.sections)


class TransitionFeature:
    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "HVAC_RectRoundTransition"
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
        add("App::PropertyLength", "Diameter", g, "D - diameter of the round end (neutral)", 400.0)
        add("App::PropertyLength", "Height", g, "H - height between rectangular and round end", 300.0)
        add("App::PropertyLength", "SideA", g, "A - AB side: rectangle edge left of the round centre", 300.0)
        add("App::PropertyLength", "SideB", g, "B - AB side: rectangle edge right of the round centre", 200.0)
        add("App::PropertyLength", "SideE", g, "E - EF side: rectangle edge above the round centre", 150.0)
        add("App::PropertyLength", "SideF", g, "F - EF side: rectangle edge below the round centre", 250.0)
        add("App::PropertyIntegerConstraint", "SectionsPerQuarter", g,
            "N - number of sections per quarter of the round", (4, 1, 90, 1))

        g = "Manufacturing Options"
        add("App::PropertyBool", "AddFoldingLines", g, "Add press-brake fold marks", True)
        add("App::PropertyLength", "FoldMarkLength", g, "Length of each fold mark", 15.0)
        add("App::PropertyLength", "FoldMarkGap", g, "Distance of the fold mark from the round edge", 2.0)
        add("App::PropertyBool", "AddReferenceDimensions", g, "Add reference dimensions", False)
        add("App::PropertyBool", "AddFoldingLabels", g, "Label the folding lines", False)
        if "SeamSide" not in have:
            obj.addProperty("App::PropertyEnumeration", "SeamSide", g,
                            "Seam position. Auto = on the longer rectangle side")
            obj.SeamSide = list(tg.SEAM_CHOICES)
            obj.SeamSide = tg.SEAM_AUTO

        g = "Preview Options"
        add("App::PropertyBool", "ShowFlatPattern", g, "Show the flat pattern in the model space", True)
        add("App::PropertyBool", "AddAnnotations", g,
            "Triangulation lines and piece name / quantity", False)

        g = "Result"
        add("App::PropertyInteger", "FoldLineCount", g, "Number of fold lines = 4 x (N + 1)", mode=1)
        add("App::PropertyString", "SeamOn", g, "Side that carries the seam", mode=1)
        add("App::PropertyLength", "SeamLength", g, "Length of the seam", mode=1)
        add("App::PropertyString", "Warning", g, "Problems found in the pattern", mode=1)

        g = "Internal"
        for part in PARTS:
            add("App::PropertyLink", "Pattern" + part, g, "", mode=2)

    @staticmethod
    def children(obj):
        return [getattr(obj, "Pattern" + p, None) for p in PARTS]

    def execute(self, obj):
        p = params_from(obj)
        errors = p.validate()
        if errors:
            raise ValueError("\n".join(errors))
        regenerate(obj, p)

    def onChanged(self, obj, prop):
        if "Restore" in getattr(obj, "State", []):
            return
        if prop in ("ShowFlatPattern", "AddFoldingLines"):
            apply_visibility(obj)

    def onDocumentRestored(self, obj):
        self.add_properties(obj)

    def dumps(self):
        return {"Type": self.Type}

    def loads(self, state):
        self.Type = "HVAC_RectRoundTransition"

    __getstate__ = dumps
    __setstate__ = loads


def regenerate(obj, p=None):
    p = p or params_from(obj)
    pat = tg.develop(p)
    opts = layout.Options(
        fold_lines=obj.AddFoldingLines,
        reference_dims=obj.AddReferenceDimensions,
        fold_labels=obj.AddFoldingLabels and obj.AddFoldingLines,
        reference_lines=obj.AddAnnotations,
        piece_labels=obj.AddAnnotations,
    )
    ref, dim, texts = transition_layout.annotations(pat, opts, params_text(p), p.diameter)
    pl = App.Placement()
    cut, folds, anno = TransitionFeature.children(obj)
    if cut:
        _set_sketch(cut, [_seg_geometry(sg) for sg in pat.contour], pl)
    if folds:
        _set_sketch(folds, [_line(a, b) for a, b in pat.fold_marks] if p.fold_lines else [], pl)
    if anno:
        anno.Placement = pl
        anno.Proxy.set_data(anno, ref, dim, texts)

    obj.FoldLineCount = len(pat.fold_lines)
    obj.SeamOn = "%s side" % pat.seam_side
    obj.SeamLength = pat.seam_length
    obj.Warning = ("Pattern overlaps itself - split it into two pieces or increase H"
                   if pat.overlaps else "")
    if pat.overlaps:
        App.Console.PrintWarning("HVAC transition: %s\n" % obj.Warning)
    apply_visibility(obj)


def apply_visibility(obj):
    if not App.GuiUp:
        return
    if any(n not in obj.PropertiesList for n in ("ShowFlatPattern", "AddFoldingLines", "PatternAnnotations")):
        return
    show = obj.ShowFlatPattern
    cut, folds, anno = TransitionFeature.children(obj)
    has_anno = bool(anno and (anno.RefLines or anno.DimLines or anno.Texts))
    for child, extra in ((cut, True), (folds, obj.AddFoldingLines), (anno, has_anno)):
        if child and child.ViewObject:
            child.ViewObject.Visibility = show and extra


class ViewProviderTransition:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        from hvacdev.freecad import resources
        return resources.icon("RectRoundTransition.svg")

    def claimChildren(self):
        return [c for c in TransitionFeature.children(self.Object) if c]

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        import FreeCADGui as Gui
        from hvacdev.freecad.transition_taskpanel import TransitionTaskPanel
        Gui.Control.showDialog(TransitionTaskPanel(vobj.Object, is_new=False))
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
        act = QtGui.QAction("Edit transition", menu)
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
    for part in PARTS:
        child = getattr(obj, "Pattern" + part, None)
        if child:
            names.append(child.Name)
            setattr(obj, "Pattern" + part, None)
    for n in names:
        if doc.getObject(n):
            doc.removeObject(n)


def make_transition(doc=None, **values):
    doc = doc or App.ActiveDocument or App.newDocument()
    obj = doc.addObject("App::FeaturePython", "Transition")
    TransitionFeature(obj)
    for k, v in values.items():
        setattr(obj, k, v)
    cut = doc.addObject("Sketcher::SketchObject", "Transition_Cut")
    folds = doc.addObject("Sketcher::SketchObject", "Transition_Folds")
    anno = annotations.make(doc, "Transition_Annotations", "Transition_Annotations")
    obj.PatternCut, obj.PatternFolds, obj.PatternAnnotations = cut, folds, anno
    if App.GuiUp:
        folds.ViewObject.LineColor = (0.85, 0.1, 0.1)
        try:
            folds.ViewObject.LineWidth = 1.5
            cut.ViewObject.LineWidth = 2.0
        except Exception:
            pass
        ViewProviderTransition(obj.ViewObject)
    update_label(obj)
    return obj


def update_label(obj):
    obj.Label = "Transition D%g H%g A%g B%g E%g F%g N%d" % (
        obj.Diameter.Value, obj.Height.Value, obj.SideA.Value, obj.SideB.Value,
        obj.SideE.Value, obj.SideF.Value, obj.SectionsPerQuarter)
