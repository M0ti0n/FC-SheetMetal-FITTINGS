"""Run with:  python -m pytest tests   (or just: python tests/test_elbow.py)"""
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hvacdev.geometry.elbow import ElbowParams, develop, summary, cut_height, segment_angle  # noqa
from hvacdev.geometry import layout, arcs  # noqa
from hvacdev.geometry.elbow import SEAM_SIDE, SEAM_POSITIONS  # noqa


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def test_segment_angle_uses_n_plus_one():
    # 90 deg, 3 middle sections -> 1/2 + 3 + 1/2 = 4 full steps of 22.5 deg
    assert approx(segment_angle(ElbowParams(angle=90, middle_sections=3)), 22.5)
    assert approx(segment_angle(ElbowParams(angle=90, middle_sections=1)), 45.0)
    assert approx(segment_angle(ElbowParams(angle=45, middle_sections=2)), 15.0)


def test_end_section_is_half_of_middle():
    p = ElbowParams(diameter=400, angle=90, radius=800, middle_sections=3)
    middle, end = develop(p)
    assert approx(middle.h_max, end.h_max)
    s = summary(p)
    assert approx(s["middle_heel"], 2 * s["end_heel"])
    assert approx(s["middle_throat"], 2 * s["end_throat"])


def test_heel_and_throat_lengths():
    p = ElbowParams(diameter=400, angle=90, radius=800, middle_sections=3)
    t = math.tan(math.radians(22.5 / 2))
    s = summary(p)
    assert approx(s["middle_heel"], 2 * 1000 * t)      # (R + r) * 2 tan
    assert approx(s["middle_throat"], 2 * 600 * t)     # (R - r) * 2 tan
    assert approx(s["developed_length"], math.pi * 400)


def test_centreline_arc_is_preserved():
    """Sum of section lengths on the side generator (= on centreline radius
    projection) must equal N+1 full steps of 2*R*tan(theta/2)."""
    p = ElbowParams(diameter=500, angle=60, radius=750, middle_sections=4)
    t = math.tan(math.radians(segment_angle(p)) / 2)
    total = p.middle_sections * 2 * p.radius * t + 2 * p.radius * t
    assert approx(total, (p.middle_sections + 1) * 2 * p.radius * t)


def test_development_matches_3d_plane_cut():
    """Independent check: intersect the cylinder with the mitre plane in 3D
    and compare the axial heights with the development."""
    p = ElbowParams(diameter=315, angle=90, radius=500, middle_sections=2, seam="Heel")  # phi = x / r
    r = p.diameter / 2
    half = math.radians(segment_angle(p)) / 2
    # Cylinder axis = y. Bend centre at x = -R (heel at +x side, x = +r).
    # The mitre plane passes through the bend centre's axis (z axis at x=-R),
    # rotated by `half` from the plane y = 0.
    for k in range(37):
        phi = 2 * math.pi * k / 36
        x = r * math.cos(phi)            # phi = 0 -> heel
        y_plane = (x + p.radius) * math.tan(half)
        xs = phi * r                     # seam at heel -> x along pattern
        assert approx(cut_height(xs, p), y_plane, 1e-9)


def test_outline_closed_and_folds_inside():
    p = ElbowParams(fold_lines=16)
    middle, end = develop(p)
    for sec in (middle, end):
        assert sec.outline[0] == sec.outline[-1]
        assert len(sec.fold_lines) == 16
        for (x, ya), (_, yb) in sec.fold_lines:
            assert 0 < x < sec.width
            assert abs(ya) <= sec.h_max + 1e-9 and abs(yb) <= sec.h_max + 1e-9
        assert approx(sec.fold_angle, 22.5)


def test_validation():
    for bad in (ElbowParams(diameter=0), ElbowParams(angle=0), ElbowParams(angle=180),
                ElbowParams(radius=100, diameter=400), ElbowParams(middle_sections=-1)):
        assert bad.validate()
    assert not ElbowParams().validate()


def test_dxf_roundtrip():
    p = ElbowParams()
    middle, end = develop(p)
    placed = layout.build(middle, end, layout.Options(), "D400 A90 R800", p.diameter)
    path = os.path.join(tempfile.mkdtemp(), "elbow.dxf")
    layout.write_dxf(placed, path)
    txt = open(path).read()
    assert txt.count("POLYLINE") == 2
    assert "AC1009" in txt and txt.strip().endswith("EOF")
    # group codes / values strictly alternate
    lines = txt.splitlines()
    assert len(lines) % 2 == 0


def test_default_seam_is_side_with_mid_length_edges():
    p = ElbowParams(diameter=400, angle=90, radius=800, middle_sections=3)
    assert p.seam == SEAM_SIDE
    middle, end = develop(p)
    t = math.tan(math.radians(22.5 / 2))
    # seam edges = side generator = centreline length (R), not throat or heel
    assert approx(cut_height(0.0, p), 800 * t)
    assert approx(cut_height(middle.width, p), 800 * t)


def test_contour_is_lines_and_arcs_within_tolerance():
    for seam in SEAM_POSITIONS:
        for d, a, r, n in ((400, 90, 800, 3), (100, 90, 100, 0), (1250, 45, 1875, 5), (160, 90, 80, 1)):
            p = ElbowParams(diameter=d, angle=a, radius=r, middle_sections=n, seam=seam)
            middle, end = develop(p)
            for sec in (middle, end):
                c = sec.contour
                assert all(isinstance(sg, arcs.Seg) for sg in c)
                # closed, gap-free chain
                for s1, s2 in zip(c, c[1:] + c[:1]):
                    assert approx(s1.end[0], s2.start[0]) and approx(s1.end[1], s2.start[1])
            curve = arcs.fit(lambda x: cut_height(x, p), 0.0, math.pi * d, p.arc_tol)
            assert arcs.max_deviation(curve, lambda x: cut_height(x, p)) <= p.arc_tol


def test_bulge_direction():
    # CCW half circle from (1,0) to (-1,0) through (0,1): bulge = tan(180/4) = +1
    assert approx(arcs.Seg((1, 0), (-1, 0), (0, 1)).bulge(), 1.0)
    assert approx(arcs.Seg((1, 0), (-1, 0), (0, -1)).bulge(), -1.0)
    assert arcs.Seg((0, 0), (1, 0)).bulge() == 0.0


def test_dxf_has_no_splines():
    p = ElbowParams()
    middle, end = develop(p)
    placed = layout.build(middle, end, layout.Options(), "x", p.diameter)
    path = os.path.join(tempfile.mkdtemp(), "e.dxf")
    layout.write_dxf(placed, path)
    txt = open(path).read()
    assert "SPLINE" not in txt
    assert txt.count("\n42\n") > 20          # arcs written as polyline bulges


def test_fold_marks_15mm_2mm_from_each_edge():
    p = ElbowParams(fold_lines=12)
    middle, end = develop(p)
    for sec, low in ((middle, None), (end, 0.0)):
        assert len(sec.fold_marks) == 2 * len(sec.fold_lines)
        for (x, ya), (_, yb) in sec.fold_lines:
            marks = sorted([m for m in sec.fold_marks if approx(m[0][0], x)], key=lambda m: m[0][1])
            (_, l0), (_, l1) = marks[0]
            (_, h0), (_, h1) = marks[1]
            assert approx(l0, min(ya, yb) + 2) and approx(l1 - l0, 15)
            assert approx(h1, max(ya, yb) - 2) and approx(h1 - h0, 15)


def test_short_piece_merges_marks():
    from hvacdev.geometry.elbow import fold_marks
    p = ElbowParams()
    assert fold_marks(0, 0, 30, p) == [((0, 2), (0, 28))]
    assert fold_marks(0, 0, 3, p) == []


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok ", name)
    print("%d tests passed" % n)
