# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parametric screw conveyor flight blank.

Tree:
    Screw flight OD315 ID101.6 P300
    ├─ ScrewFlight_Cut          <- Sketch: blank (ring with gap, arcs + 2 lines)
    └─ ScrewFlight_Annotations  <- end of the calculated part, dimensions, label
"""

import FreeCAD as App

from hvacdev.geometry import screw as sg
from hvacdev.geometry import screw_layout
from hvacdev.geometry import layout
from hvacdev.freecad import annotations
from hvacdev.freecad.elbow_feature import _seg_geometry, _set_sketch

PARTS = ("Cut", "Annotations")


def params_from(obj):
    return sg.ScrewParams(od=float(obj.OuterDiameter.Value), id=float(obj.InnerDiameter.Value),
                          pitch=float(obj.Pitch.Value), length=float(obj.ScrewLength.Value),
                          gap=float(obj.Gap.Value))


class ScrewFeature:
    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "HVAC_ScrewFlight"
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
        add("App::PropertyLength", "OuterDiameter", g, "OD - outer diameter of the flight", 315.0)
        add("App::PropertyLength", "InnerDiameter", g, "ID - inner diameter of the flight (shaft)", 101.6)
        add("App::PropertyLength", "Pitch", g, "P - pitch, one turn along the axis", 300.0)
        add("App::PropertyLength", "ScrewLength", g, "L - screw length (number of pieces = L / P)", 1000.0)
        add("App::PropertyLength", "Gap", g,
            "Gap between the cut ends at the inner edge; the blank is extended until this gap is left", 6.0)

        g = "Flat Pattern Options"
        add("App::PropertyBool", "AddReferenceDimensions", g, "Add reference dimensions", False)

        g = "Preview Options"
        add("App::PropertyBool", "ShowFlatPattern", g, "Show the blank in the model space", True)
        add("App::PropertyBool", "AddAnnotations", g,
            "Centre lines, end of the calculated part (extension) and piece label", False)

        g = "Result"
        for name, doc in (("BlankInnerRadius", "Inner radius of the blank"),
                          ("BlankOuterRadius", "Outer radius of the blank"),
                          ("OuterGap", "Gap between the cut ends at the outer edge")):
            add("App::PropertyLength", name, g, doc, mode=1)
        for name, doc in (("CalculatedAngle", "Calculated blank angle for one pitch"),
                          ("BlankAngle", "Blank angle to cut (calculated + extension)"),
                          ("Extension", "Extension added to the calculated angle")):
            add("App::PropertyAngle", name, g, doc, mode=1)
        add("App::PropertyInteger", "Pieces", g, "Number of pieces = L / P rounded up", mode=1)
        add("App::PropertyString", "Warning", g, "Problems found", mode=1)

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
        if prop == "ShowFlatPattern":
            apply_visibility(obj)

    def onDocumentRestored(self, obj):
        self.add_properties(obj)

    def dumps(self):
        return {"Type": self.Type}

    def loads(self, state):
        self.Type = "HVAC_ScrewFlight"

    __getstate__ = dumps
    __setstate__ = loads


def regenerate(obj, p=None):
    p = p or params_from(obj)
    blank = sg.develop(p)
    r = blank.result
    opts = layout.Options(fold_lines=False, reference_dims=obj.AddReferenceDimensions, fold_labels=False,
                          reference_lines=obj.AddAnnotations, piece_labels=obj.AddAnnotations)
    ref, dim, texts = screw_layout.annotations(blank, p, opts)
    pl = App.Placement()
    cut, anno = ScrewFeature.children(obj)
    if cut:
        _set_sketch(cut, [_seg_geometry(s) for s in blank.contour], pl)
    if anno:
        anno.Placement = pl
        anno.Proxy.set_data(anno, ref, dim, texts)
    obj.BlankInnerRadius = r.ri
    obj.BlankOuterRadius = r.ro
    obj.OuterGap = r.gap_outer
    obj.CalculatedAngle = r.calc_angle
    obj.BlankAngle = r.blank_angle
    obj.Extension = r.extension
    obj.Pieces = r.pieces
    obj.Warning = " ".join(r.warnings)
    if r.warnings:
        App.Console.PrintWarning("HVAC screw flight: %s\n" % obj.Warning)
    apply_visibility(obj)


def apply_visibility(obj):
    if not App.GuiUp:
        return
    if any(n not in obj.PropertiesList for n in ("ShowFlatPattern", "PatternAnnotations")):
        return
    cut, anno = ScrewFeature.children(obj)
    has_anno = bool(anno and (anno.RefLines or anno.DimLines or anno.Texts))
    for child, extra in ((cut, True), (anno, has_anno)):
        if child and child.ViewObject:
            child.ViewObject.Visibility = obj.ShowFlatPattern and extra


class ViewProviderScrew:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        from hvacdev.freecad import resources
        return resources.icon("ScrewFlight.svg")

    def claimChildren(self):
        return [c for c in ScrewFeature.children(self.Object) if c]

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        import FreeCADGui as Gui
        from hvacdev.freecad.screw_taskpanel import ScrewTaskPanel
        Gui.Control.showDialog(ScrewTaskPanel(vobj.Object, is_new=False))
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
        act = QtGui.QAction("Edit screw flight", menu)
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


def make_screw(doc=None, **values):
    doc = doc or App.ActiveDocument or App.newDocument()
    obj = doc.addObject("App::FeaturePython", "ScrewFlight")
    ScrewFeature(obj)
    for k, v in values.items():
        setattr(obj, k, v)
    cut = doc.addObject("Sketcher::SketchObject", "ScrewFlight_Cut")
    anno = annotations.make(doc, "ScrewFlight_Annotations", "ScrewFlight_Annotations")
    obj.PatternCut, obj.PatternAnnotations = cut, anno
    if App.GuiUp:
        try:
            cut.ViewObject.LineWidth = 2.0
        except Exception:
            pass
        ViewProviderScrew(obj.ViewObject)
    update_label(obj)
    return obj


def update_label(obj):
    obj.Label = "Screw flight OD%g ID%g P%g" % (obj.OuterDiameter.Value, obj.InnerDiameter.Value,
                                                obj.Pitch.Value)
