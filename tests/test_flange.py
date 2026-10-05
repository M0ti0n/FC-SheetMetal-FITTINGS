"""Run with:  python tests/test_flange.py   (no FreeCAD needed)"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hvacdev.geometry.flange import (FlangeParams, develop, params_for, table_row,  # noqa
                                     SLOT_LENGTH)
from hvacdev.geometry.flange_table import SIZES  # noqa
from hvacdev.geometry import flange_layout, layout  # noqa
from hvacdev.geometry.arcs import circle_through  # noqa


def closed(c):
    return all(math.dist(s1.end, s2.start) < 1e-9 for s1, s2 in zip(c, c[1:] + c[:1]))


def test_every_table_size_develops():
    assert len(SIZES) == 44
    for A, B, M, N, E, T in SIZES:
        p, from_table = params_for(A)
        assert from_table and (p.b, p.m, p.n, p.e, p.t) == (B, M, N, E, T)
        assert not p.validate(), (A, p.validate())
        pat = develop(p)
        assert len(pat.slots) == N
        for c in pat.contours:
            assert closed(c) and all(s.is_arc for s in c)


def test_diameters():
    p, _ = params_for(400)
    pat = develop(p)
    cx, cy = pat.centre
    assert abs(math.dist(pat.outer[0].start, pat.centre) - (400 + 2 * 30) / 2) < 1e-9
    assert abs(math.dist(pat.inner[0].start, pat.centre) - 200) < 1e-9
    assert pat.bbox() == (0.0, 0.0, 460.0, 460.0)


def test_slot_geometry():
    p, _ = params_for(400)          # B 435, M 11, N 10
    pat = develop(p)
    for k in range(p.n):
        h = pat.hole_centres[3 * k: 3 * k + 3]
        assert abs(math.dist(h[0], h[2]) - SLOT_LENGTH) < 1e-9          # 25 mm between end holes
        for q in h:
            assert abs(math.dist(q, pat.centre) - p.b / 2) < 1e-9        # on the B circle
        outer, cap1, inner, cap2 = pat.slots[k]
        for s, r in ((outer, p.b / 2 + p.m / 2), (inner, p.b / 2 - p.m / 2)):
            (ccx, ccy), rr = circle_through(s.start, s.mid, s.end)
            assert abs(rr - r) < 1e-6 and math.dist((ccx, ccy), pat.centre) < 1e-6
        for cap in (cap1, cap2):
            _, rr = circle_through(cap.start, cap.mid, cap.end)
            assert abs(rr - p.m / 2) < 1e-9                              # width M


def test_equal_spacing_first_slot_on_top():
    for A in (80, 120, 400, 820):
        p, _ = params_for(A)
        pat = develop(p)
        ang = pat.slot_angles
        assert abs(ang[0] - 90.0) < 1e-9
        steps = [(b - a) % 360 for a, b in zip(ang, ang[1:] + ang[:1])]
        assert all(abs(s - 360.0 / p.n) < 1e-9 for s in steps)


def test_slot_caps_bulge_outwards():
    p, _ = params_for(200)
    pat = develop(p)
    for k, slot in enumerate(pat.slots):
        mid_hole = pat.hole_centres[3 * k + 1]
        for cap, end_hole in ((slot[1], pat.hole_centres[3 * k + 2]), (slot[3], pat.hole_centres[3 * k])):
            # cap middle point is farther from the slot middle than the end-hole centre
            assert math.dist(cap.mid, mid_hole) > math.dist(end_hole, mid_hole)


def test_custom_size_uses_nearest_smaller_row():
    p, from_table = params_for(410)                 # between 400 and 420
    assert not from_table
    assert (p.b, p.m, p.n, p.e, p.t) == (410 + 35, 11, 10, 30, 8)
    p, _ = params_for(50)                           # below the table: first row as template
    assert p.b == 50 + 31 and p.n == 4
    assert table_row(400) and not table_row(410)


def test_validation():
    assert FlangeParams(a=400, b=410, m=11, n=10, e=30).validate()       # slots cut the inner edge
    assert FlangeParams(a=400, b=455, m=11, n=10, e=30).validate()       # slots cut the outer edge
    assert FlangeParams(a=80, b=111, m=9, n=12, e=25).validate()         # too many slots
    assert not FlangeParams(a=80, b=111, m=9, n=4, e=25).validate()
    for bad in (dict(a=0), dict(e=0), dict(m=0), dict(n=0)):
        assert FlangeParams(**bad).validate()


def test_d_and_t_only_with_annotations_or_dimensions():
    p, _ = params_for(400)
    pat = develop(p)
    ref, dim, texts = flange_layout.annotations(pat, p, layout.Options())
    assert not ref and not dim and not texts
    for opts in (layout.Options(reference_dims=True),
                 layout.Options(reference_lines=True, piece_labels=True)):
        _, _, texts = flange_layout.annotations(pat, p, opts)
        joined = " ".join(t[1] for t in texts)
        assert "D 460" in joined and "T 8" in joined


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok ", name)
    print("%d tests passed" % n)
