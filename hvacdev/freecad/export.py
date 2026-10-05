# SPDX-License-Identifier: LGPL-2.1-or-later
"""DXF export of what is currently shown in the model space.

Reads the real sketches (so manual sketch edits / moves are exported) and the
annotation objects, and writes one R12 DXF with layers CUT / FOLD / REF /
DIM / TEXT.
"""

import FreeCAD as App

from hvacdev.dxf.writer import DxfWriter
from hvacdev.geometry.arcs import Seg
from hvacdev.freecad.annotations import PatternAnnotation
from hvacdev.freecad.elbow_feature import SECTIONS, ElbowFeature

DEFLECTION = 0.02   # mm, max chord error when discretising curves


def _visible(o):
    return o is not None and (not App.GuiUp or o.ViewObject.Visibility)


def _xy(v):
    return (v.x, v.y)


def _close(a, b, tol=1e-6):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def wire_to_polyline(wire):
    """Vertices + DXF bulges for a wire. Lines and circular arcs are kept
    exact; anything else (e.g. a spline drawn by hand) is broken into short
    straight segments - the DXF never contains a spline."""
    pts, bulges = [], []
    edges = wire.OrderedEdges
    verts = [_xy(v.Point) for v in wire.OrderedVertexes]
    for i, e in enumerate(edges):
        p0 = verts[i] if i < len(verts) else _xy(e.Vertexes[0].Point)
        p1 = verts[(i + 1) % len(verts)] if (i + 1 < len(verts) or wire.isClosed()) \
            else _xy(e.Vertexes[-1].Point)
        ctype = type(e.Curve).__name__
        if ctype == "Line":
            pts.append(p0)
            bulges.append(0.0)
        elif ctype == "Circle":
            pm = _xy(e.valueAt(0.5 * (e.FirstParameter + e.LastParameter)))
            pts.append(p0)
            bulges.append(Seg(p0, p1, pm).bulge())
        else:
            dpts = [_xy(v) for v in e.discretize(Deflection=DEFLECTION)]
            if not _close(dpts[0], p0):
                dpts.reverse()
            pts.extend(dpts[:-1])
            bulges.extend([0.0] * (len(dpts) - 1))
    if not wire.isClosed():
        pts.append(verts[-1])
        bulges.append(0.0)
    return pts, bulges


def visible_sections(obj):
    out = []
    for s in SECTIONS:
        cut, folds, anno = ElbowFeature.children(obj, s)
        if _visible(cut):
            out.append((s, cut, folds if _visible(folds) else None,
                        anno if _visible(anno) else None))
    return out


def export_elbow(obj, path):
    sections = visible_sections(obj)
    if not sections:
        raise RuntimeError("No flat pattern is visible - tick Middle sec. or End sec. first.")
    return export_sections(sections, path)


def export_transition(obj, path):
    from hvacdev.freecad.transition_feature import TransitionFeature
    cut, folds, anno = TransitionFeature.children(obj)
    if not _visible(cut):
        raise RuntimeError("The flat pattern is hidden - tick Show flat pattern first.")
    if not getattr(obj, "Pieces", "x"):
        raise RuntimeError("No pattern selected - tick Combined, Short Side or Long Side.")
    return export_sections([("Transition", cut, folds if _visible(folds) else None,
                             anno if _visible(anno) else None)], path)


def export_sections(sections, path, fold_layer="FOLD"):
    """sections: [(name, cut_sketch, folds_sketch or None, annotations or None)];
    the second sketch goes to `fold_layer` (FOLD, or MARK for drill crosses)."""
    w = DxfWriter()
    for _name, cut, folds, anno in sections:
        for wire in cut.Shape.Wires:
            pts, bulges = wire_to_polyline(wire)
            w.polyline(pts, "CUT", closed=wire.isClosed(), bulges=bulges)
        if folds is not None:
            for wire in folds.Shape.Wires:
                pts, bulges = wire_to_polyline(wire)
                if len(pts) == 2 and not any(bulges):
                    w.line(pts[0], pts[1], fold_layer)
                else:
                    w.polyline(pts, fold_layer, closed=wire.isClosed(), bulges=bulges)
        if anno is not None:
            pl = anno.Placement

            def g(p):
                return _xy(pl.multVec(App.Vector(p[0], p[1], 0)))

            rot = pl.Rotation.Angle * (1 if pl.Rotation.Axis.z >= 0 else -1)
            import math
            rot_deg = math.degrees(rot)
            for a, b in PatternAnnotation.ref_lines(anno):
                w.line(g(a), g(b), "REF")
            for a, b in PatternAnnotation.dim_lines(anno):
                w.line(g(a), g(b), "DIM")
            for pos, value, h, r in PatternAnnotation.texts(anno):
                w.text(g(pos), value, h, rotation=r + rot_deg, center=(r == 0.0))
    w.save(path)
    return [s[0] for s in sections]


def export_branch_reducer(obj, path):
    from hvacdev.freecad.branch_feature import SECTIONS as BR_SECTIONS, BranchReducerFeature
    sections = []
    for s in BR_SECTIONS:
        cut, folds, anno = BranchReducerFeature.children(obj, s)
        if _visible(cut):
            sections.append((s, cut, folds if _visible(folds) else None,
                             anno if _visible(anno) else None))
    if not sections:
        raise RuntimeError("No flat pattern is visible - tick Reducer or Branch first.")
    return export_sections(sections, path)


def export_flange(obj, path):
    from hvacdev.geometry.flange_divide import can_divide
    if not getattr(obj, "ShowCombined", True) and not (
            getattr(obj, "ShowDivided", False) and can_divide(obj.Diameter.Value, _hole_count(obj))):
        raise RuntimeError("Nothing to export - tick Combined or Divided.")
    from hvacdev.freecad.flange_feature import FlangeFeature
    cut, anno = FlangeFeature.children(obj)
    if not _visible(cut):
        raise RuntimeError("The flat pattern is hidden - tick Show flat pattern first.")
    return export_sections([("Flange", cut, None, anno if _visible(anno) else None)], path)


def export_thread_flange(obj, path):
    from hvacdev.geometry.flange_divide import can_divide
    if not getattr(obj, "ShowCombined", True) and not (
            getattr(obj, "ShowDivided", False) and can_divide(obj.Diameter.Value, _hole_count(obj))):
        raise RuntimeError("Nothing to export - tick Combined or Divided.")
    from hvacdev.freecad.flange_thread_feature import ThreadFlangeFeature
    cut, marks, anno = ThreadFlangeFeature.children(obj)
    if not _visible(cut):
        raise RuntimeError("The flat pattern is hidden - tick Show flat pattern first.")
    return export_sections([("Flange", cut, marks if _visible(marks) else None,
                             anno if _visible(anno) else None)], path, fold_layer="MARK")


def _hole_count(obj):
    return int(getattr(obj, "SlotCount", getattr(obj, "HoleCount", 0)))
