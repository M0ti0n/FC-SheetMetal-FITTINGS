# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lightweight annotation object: reference lines, dimension lines and text.

Shown in the 3D view with plain Coin nodes (no Draft objects, so the tree
stays clean: one annotation object per pattern instead of 50 text labels).
All coordinates are local; the object's Placement positions them, exactly
like the matching sketch.
"""

import math

import FreeCAD as App

TEXT_SEP = "|"


def encode_text(pos, value, height, rotation):
    return TEXT_SEP.join(("%.4f" % pos[0], "%.4f" % pos[1], "%.4f" % height,
                          "%.4f" % rotation, value.replace(TEXT_SEP, "/")))


def decode_text(s):
    x, y, h, rot, value = s.split(TEXT_SEP, 4)
    return (float(x), float(y)), value, float(h), float(rot)


def _pairs(vectors):
    return [((vectors[i].x, vectors[i].y), (vectors[i + 1].x, vectors[i + 1].y))
            for i in range(0, len(vectors) - 1, 2)]


class PatternAnnotation:
    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "HVAC_PatternAnnotation"
        self._add_properties(obj)

    @staticmethod
    def _add_properties(obj):
        props = obj.PropertiesList
        if "Placement" not in props:
            obj.addProperty("App::PropertyPlacement", "Placement", "Base", "Position on the sheet")
        if "RefLines" not in props:
            obj.addProperty("App::PropertyVectorList", "RefLines", "Annotation",
                            "Reference / centre lines (pairs of points)")
        if "DimLines" not in props:
            obj.addProperty("App::PropertyVectorList", "DimLines", "Annotation",
                            "Dimension lines (pairs of points)")
        if "Texts" not in props:
            obj.addProperty("App::PropertyStringList", "Texts", "Annotation",
                            "x|y|height|rotation|text")
        for p in ("RefLines", "DimLines", "Texts"):
            obj.setEditorMode(p, 1)  # read only

    def set_data(self, obj, ref_lines, dim_lines, texts):
        V = App.Vector
        obj.RefLines = [V(x, y, 0) for seg in ref_lines for (x, y) in seg]
        obj.DimLines = [V(x, y, 0) for seg in dim_lines for (x, y) in seg]
        obj.Texts = [encode_text(*t) for t in texts]

    # helpers used by the DXF export
    @staticmethod
    def ref_lines(obj):
        return _pairs(obj.RefLines)

    @staticmethod
    def dim_lines(obj):
        return _pairs(obj.DimLines)

    @staticmethod
    def texts(obj):
        return [decode_text(s) for s in obj.Texts]

    def execute(self, obj):
        pass

    def onDocumentRestored(self, obj):
        self._add_properties(obj)

    # FreeCAD 0.21 and 1.x serialisation
    def dumps(self):
        return {"Type": self.Type}

    def loads(self, state):
        self.Type = "HVAC_PatternAnnotation"

    __getstate__ = dumps
    __setstate__ = loads


class ViewProviderPatternAnnotation:
    REF_COLOR = (0.15, 0.6, 0.15)
    DIM_COLOR = (0.0, 0.55, 0.65)
    TEXT_COLOR = (0.85, 0.45, 0.0)

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        from pivy import coin
        self.Object = vobj.Object
        self.root = coin.SoSeparator()
        self.transform = coin.SoTransform()
        self.content = coin.SoSeparator()
        self.root.addChild(self.transform)
        self.root.addChild(self.content)
        vobj.addDisplayMode(self.root, "Default")
        self._rebuild(vobj.Object)

    def getDisplayModes(self, vobj):
        return ["Default"]

    def getDefaultDisplayMode(self):
        return "Default"

    def setDisplayMode(self, mode):
        return mode

    def updateData(self, obj, prop):
        if prop in ("Placement", "RefLines", "DimLines", "Texts"):
            self._rebuild(obj)

    def onChanged(self, vobj, prop):
        pass

    def _lines(self, segments, color, dashed):
        from pivy import coin
        sep = coin.SoSeparator()
        col = coin.SoBaseColor()
        col.rgb = color
        style = coin.SoDrawStyle()
        style.lineWidth = 1
        if dashed:
            style.linePattern = 0xF0F0
        coords = coin.SoCoordinate3()
        pts = [(x, y, 0.0) for seg in segments for (x, y) in seg]
        coords.point.setValues(0, len(pts), pts)
        ls = coin.SoLineSet()
        ls.numVertices.setValues(0, len(segments), [2] * len(segments))
        for n in (col, style, coords, ls):
            sep.addChild(n)
        return sep

    def _text(self, pos, value, height, rotation):
        from pivy import coin
        sep = coin.SoSeparator()
        tr = coin.SoTransform()
        tr.translation.setValue(pos[0], pos[1], 0.0)
        tr.rotation.setValue(coin.SbVec3f(0, 0, 1), math.radians(rotation))
        col = coin.SoBaseColor()
        col.rgb = self.TEXT_COLOR
        font = coin.SoFont()
        font.size = height
        txt = coin.SoAsciiText()
        txt.string = value
        if rotation == 0.0:
            txt.justification = coin.SoAsciiText.CENTER
            tr.translation.setValue(pos[0], pos[1] - height * 0.35, 0.0)
        for n in (tr, col, font, txt):
            sep.addChild(n)
        return sep

    def _rebuild(self, obj):
        if not hasattr(self, "content"):
            return
        from pivy import coin
        self.content.removeAllChildren()
        pl = obj.Placement
        self.transform.translation.setValue(pl.Base.x, pl.Base.y, pl.Base.z)
        self.transform.rotation.setValue(coin.SbRotation(*pl.Rotation.Q))
        refs = PatternAnnotation.ref_lines(obj)
        dims = PatternAnnotation.dim_lines(obj)
        if refs:
            self.content.addChild(self._lines(refs, self.REF_COLOR, True))
        if dims:
            self.content.addChild(self._lines(dims, self.DIM_COLOR, False))
        for t in PatternAnnotation.texts(obj):
            self.content.addChild(self._text(*t))

    def getIcon(self):
        from hvacdev.freecad import resources
        return resources.icon("Annotation.svg")

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def make(doc, name, label):
    obj = doc.addObject("App::FeaturePython", name)
    obj.Label = label
    PatternAnnotation(obj)
    if App.GuiUp:
        ViewProviderPatternAnnotation(obj.ViewObject)
    return obj
