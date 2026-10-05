# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parametric flat ring flange with arc slots.

Tree:
    Flange A400
    ├─ Flange_Cut          <- Sketch: outer circle, inner circle, N slots (arcs only)
    └─ Flange_Annotations  <- centre lines, B circle, hole centres, dimensions, labels
"""

import FreeCAD as App

from hvacdev.geometry import flange as fg
from hvacdev.geometry import flange_layout
from hvacdev.geometry import layout
from hvacdev.freecad import annotations
from hvacdev.freecad.elbow_feature import _seg_geometry, _set_sketch

PARTS = ("Cut", "Annotations")


def params_from(obj):
    return fg.FlangeParams(a=float(obj.Diameter.Value), b=float(obj.SlotCircle.Value),
                           m=float(obj.SlotWidth.Value), n=int(obj.SlotCount),
                           e=float(obj.RingWidth.Value), t=float(obj.Thickness.Value))


class FlangeFeature:
    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "HVAC_Flange"
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

        p, _ = fg.params_for(400)
        g = "Main Parameters"
        add("App::PropertyLength", "Diameter", g, "A - inner (nominal) diameter", p.a)
        add("App::PropertyLength", "SlotCircle", g, "B - diameter the slots lie on", p.b)
        add("App::PropertyLength", "SlotWidth", g, "M - slot width (slots are 25 mm between end holes)", p.m)
        add("App::PropertyIntegerConstraint", "SlotCount", g, "N - number of slots, equally spaced",
            (p.n, 1, 360, 1))
        add("App::PropertyLength", "RingWidth", g, "E - ring width; outer diameter D = A + 2E", p.e)
        add("App::PropertyLength", "Thickness", g, "T - recommended thickness (information only)", p.t)

        g = "Flat Pattern Options"
        add("App::PropertyBool", "AddReferenceDimensions", g, "Add reference dimensions (incl. D and T)", False)

        g = "Preview Options"
        add("App::PropertyBool", "ShowFlatPattern", g, "Show the flat pattern in the model space", True)
        add("App::PropertyBool", "AddAnnotations", g,
            "Centre lines, B circle, hole centres and piece label (incl. D and T)", False)

        g = "Result"
        add("App::PropertyLength", "OuterDiameter", g, "D = A + 2E (information)", mode=1)
        add("App::PropertyBool", "StandardSize", g, "A is a size from the table", mode=1)

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
        self.Type = "HVAC_Flange"

    __getstate__ = dumps
    __setstate__ = loads


def regenerate(obj, p=None):
    p = p or params_from(obj)
    pat = fg.develop(p)
    opts = layout.Options(fold_lines=False, reference_dims=obj.AddReferenceDimensions,
                          fold_labels=False, reference_lines=obj.AddAnnotations,
                          piece_labels=obj.AddAnnotations)
    ref, dim, texts = flange_layout.annotations(pat, p, opts)
    pl = App.Placement()
    cut, anno = FlangeFeature.children(obj)
    if cut:
        _set_sketch(cut, [_seg_geometry(sg) for c in pat.contours for sg in c], pl)
    if anno:
        anno.Placement = pl
        anno.Proxy.set_data(anno, ref, dim, texts)
    obj.OuterDiameter = p.d
    obj.StandardSize = fg.table_row(p.a) is not None
    apply_visibility(obj)


def apply_visibility(obj):
    if not App.GuiUp:
        return
    if any(n not in obj.PropertiesList for n in ("ShowFlatPattern", "PatternAnnotations")):
        return
    show = obj.ShowFlatPattern
    cut, anno = FlangeFeature.children(obj)
    has_anno = bool(anno and (anno.RefLines or anno.DimLines or anno.Texts))
    for child, extra in ((cut, True), (anno, has_anno)):
        if child and child.ViewObject:
            child.ViewObject.Visibility = show and extra


class ViewProviderFlange:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        from hvacdev.freecad import resources
        return resources.icon("Flange.svg")

    def claimChildren(self):
        return [c for c in FlangeFeature.children(self.Object) if c]

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        import FreeCADGui as Gui
        from hvacdev.freecad.flange_taskpanel import FlangeTaskPanel
        Gui.Control.showDialog(FlangeTaskPanel(vobj.Object, is_new=False))
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
        act = QtGui.QAction("Edit flange", menu)
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


def make_flange(doc=None, **values):
    doc = doc or App.ActiveDocument or App.newDocument()
    obj = doc.addObject("App::FeaturePython", "Flange")
    FlangeFeature(obj)
    for k, v in values.items():
        setattr(obj, k, v)
    cut = doc.addObject("Sketcher::SketchObject", "Flange_Cut")
    anno = annotations.make(doc, "Flange_Annotations", "Flange_Annotations")
    obj.PatternCut, obj.PatternAnnotations = cut, anno
    if App.GuiUp:
        try:
            cut.ViewObject.LineWidth = 2.0
        except Exception:
            pass
        ViewProviderFlange(obj.ViewObject)
    update_label(obj)
    return obj


def update_label(obj):
    obj.Label = "Flange A%g" % obj.Diameter.Value
