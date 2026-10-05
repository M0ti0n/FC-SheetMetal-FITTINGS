# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parametric flat ring flange with drill & tap cross marks.

Tree:
    Flange M8 A400
    ├─ ThreadFlange_Cut          <- Sketch: outer and inner circle (arcs only)
    ├─ ThreadFlange_Marks        <- Sketch: X marks at the hole positions (DXF layer MARK)
    └─ ThreadFlange_Annotations  <- centre lines, B circle, dimensions, labels
"""

import FreeCAD as App

from hvacdev.geometry import flange_thread as tg
from hvacdev.geometry import flange_thread_layout
from hvacdev.geometry import layout
from hvacdev.geometry.flange_thread_table import THREADS
from hvacdev.freecad import annotations
from hvacdev.freecad.elbow_feature import _line, _seg_geometry, _set_sketch

PARTS = ("Cut", "Marks", "Annotations")


def params_from(obj):
    return tg.ThreadFlangeParams(a=float(obj.Diameter.Value), b=float(obj.HoleCircle.Value),
                                 m=str(obj.Thread), n=int(obj.HoleCount),
                                 e=float(obj.RingWidth.Value), t=float(obj.Thickness.Value),
                                 mark_size=float(obj.MarkSize.Value))


class ThreadFlangeFeature:
    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "HVAC_ThreadFlange"
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

        p, _ = tg.params_for(400)
        g = "Main Parameters"
        add("App::PropertyLength", "Diameter", g, "A - inner (nominal) diameter", p.a)
        add("App::PropertyLength", "HoleCircle", g, "B - diameter the holes lie on", p.b)
        add("App::PropertyString", "Thread", g, "M - metric thread of the holes (drill & tap)", p.m)
        add("App::PropertyIntegerConstraint", "HoleCount", g, "N - number of holes, equally spaced",
            (p.n, 1, 360, 1))
        add("App::PropertyLength", "RingWidth", g, "E - ring width; outer diameter D = A + 2E", p.e)
        add("App::PropertyLength", "Thickness", g, "T - recommended thickness (information only)", p.t)

        g = "Flat Pattern Options"
        add("App::PropertyBool", "AddMarks", g, "Add the drill & tap cross marks", True)
        add("App::PropertyLength", "MarkSize", g, "Overall size of a cross mark", 10.0)
        add("App::PropertyBool", "AddReferenceDimensions", g, "Add reference dimensions (incl. D and T)", False)

        g = "Preview Options"
        add("App::PropertyBool", "ShowFlatPattern", g, "Show the flat pattern in the model space", True)
        add("App::PropertyBool", "AddAnnotations", g,
            "Centre lines, B circle and piece label (incl. D and T)", False)

        g = "Result"
        add("App::PropertyLength", "OuterDiameter", g, "D = A + 2E (information)", mode=1)
        add("App::PropertyLength", "TapDrill", g, "Tap drill for the thread", mode=1)
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
        if prop in ("ShowFlatPattern", "AddMarks"):
            apply_visibility(obj)

    def onDocumentRestored(self, obj):
        self.add_properties(obj)

    def dumps(self):
        return {"Type": self.Type}

    def loads(self, state):
        self.Type = "HVAC_ThreadFlange"

    __getstate__ = dumps
    __setstate__ = loads


def regenerate(obj, p=None):
    p = p or params_from(obj)
    pat = tg.develop(p)
    opts = layout.Options(fold_lines=False, reference_dims=obj.AddReferenceDimensions,
                          fold_labels=False, reference_lines=obj.AddAnnotations,
                          piece_labels=obj.AddAnnotations)
    ref, dim, texts = flange_thread_layout.annotations(pat, p, opts)
    pl = App.Placement()
    cut, marks, anno = ThreadFlangeFeature.children(obj)
    if cut:
        _set_sketch(cut, [_seg_geometry(sg) for c in pat.contours for sg in c], pl)
    if marks:
        _set_sketch(marks, [_line(a, b) for a, b in pat.marks] if obj.AddMarks else [], pl)
    if anno:
        anno.Placement = pl
        anno.Proxy.set_data(anno, ref, dim, texts)
    obj.OuterDiameter = p.d
    obj.TapDrill = tg.tap_drill(p.m)
    obj.StandardSize = tg.table_row(p.a) is not None
    apply_visibility(obj)


def apply_visibility(obj):
    if not App.GuiUp:
        return
    if any(n not in obj.PropertiesList for n in ("ShowFlatPattern", "AddMarks", "PatternAnnotations")):
        return
    show = obj.ShowFlatPattern
    cut, marks, anno = ThreadFlangeFeature.children(obj)
    has_anno = bool(anno and (anno.RefLines or anno.DimLines or anno.Texts))
    for child, extra in ((cut, True), (marks, obj.AddMarks), (anno, has_anno)):
        if child and child.ViewObject:
            child.ViewObject.Visibility = show and extra


class ViewProviderThreadFlange:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        from hvacdev.freecad import resources
        return resources.icon("ThreadFlange.svg")

    def claimChildren(self):
        return [c for c in ThreadFlangeFeature.children(self.Object) if c]

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        import FreeCADGui as Gui
        from hvacdev.freecad.flange_thread_taskpanel import ThreadFlangeTaskPanel
        Gui.Control.showDialog(ThreadFlangeTaskPanel(vobj.Object, is_new=False))
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
        act = QtGui.QAction("Edit threaded flange", menu)
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


def make_thread_flange(doc=None, **values):
    doc = doc or App.ActiveDocument or App.newDocument()
    obj = doc.addObject("App::FeaturePython", "ThreadFlange")
    ThreadFlangeFeature(obj)
    for k, v in values.items():
        setattr(obj, k, v)
    cut = doc.addObject("Sketcher::SketchObject", "ThreadFlange_Cut")
    marks = doc.addObject("Sketcher::SketchObject", "ThreadFlange_Marks")
    anno = annotations.make(doc, "ThreadFlange_Annotations", "ThreadFlange_Annotations")
    obj.PatternCut, obj.PatternMarks, obj.PatternAnnotations = cut, marks, anno
    if App.GuiUp:
        try:
            cut.ViewObject.LineWidth = 2.0
            marks.ViewObject.LineColor = (0.75, 0.1, 0.75)
            marks.ViewObject.LineWidth = 1.5
        except Exception:
            pass
        ViewProviderThreadFlange(obj.ViewObject)
    update_label(obj)
    return obj


def update_label(obj):
    obj.Label = "Flange %s A%g" % (str(obj.Thread).upper(), obj.Diameter.Value)


THREAD_CHOICES = list(THREADS)
