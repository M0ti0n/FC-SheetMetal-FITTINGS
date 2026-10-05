"""Run with:  python tests/test_flange_thread.py   (no FreeCAD needed)"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hvacdev.geometry.flange_thread import (ThreadFlangeParams, develop, params_for, table_row,  # noqa
                                            thread_diameter, tap_drill)
from hvacdev.geometry.flange_thread_table import SIZES  # noqa
from hvacdev.geometry import flange_thread_layout, layout  # noqa


def test_every_table_size_develops():
    assert len(SIZES) == 44
    for A, B, M, N, E, T in SIZES:
        p, std = params_for(A)
        assert std and (p.b, p.m, p.n, p.e, p.t) == (B, M, N, E, T)
        assert not p.validate(), (A, p.validate())
        pat = develop(p)
        assert len(pat.hole_centres) == N and len(pat.marks) == 2 * N
        for c in pat.contours:
            assert all(s.is_arc for s in c)
            assert all(math.dist(s1.end, s2.start) < 1e-9 for s1, s2 in zip(c, c[1:] + c[:1]))


def test_holes_on_b_circle_equally_spaced_first_on_top():
    for A in (80, 400, 820):
        p, _ = params_for(A)
        pat = develop(p)
        for h in pat.hole_centres:
            assert abs(math.dist(h, pat.centre) - p.b / 2) < 1e-9
        assert abs(pat.hole_angles[0] - 90) < 1e-9
        ang = pat.hole_angles
        steps = [(b - a) % 360 for a, b in zip(ang, ang[1:] + ang[:1])]
        assert all(abs(s - 360.0 / p.n) < 1e-9 for s in steps)


def test_cross_marks_are_x_centred_on_the_holes():
    p, _ = params_for(400)
    p.mark_size = 12
    pat = develop(p)
    for k, h in enumerate(pat.hole_centres):
        (a1, b1), (a2, b2) = pat.marks[2 * k], pat.marks[2 * k + 1]
        for a, b in ((a1, b1), (a2, b2)):
            assert abs(math.dist(a, b) - 12) < 1e-9
            assert math.dist(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), h) < 1e-9
        v1 = (b1[0] - a1[0], b1[1] - a1[1])
        v2 = (b2[0] - a2[0], b2[1] - a2[1])
        assert abs(v1[0] * v2[0] + v1[1] * v2[1]) < 1e-9            # arms at 90 deg
        rad = (h[0] - pat.centre[0], h[1] - pat.centre[1])
        cosang = abs(v1[0] * rad[0] + v1[1] * rad[1]) / (math.hypot(*v1) * math.hypot(*rad))
        assert abs(cosang - math.cos(math.pi / 4)) < 1e-9           # 45 deg to the radius -> X


def test_threads_and_tap_drills():
    assert thread_diameter("M8") == 8 and tap_drill("M8") == 6.8
    assert tap_drill("m6") == 5.0 and tap_drill("M10") == 8.5
    assert thread_diameter("M7") == 7 and tap_drill("M7") == 5.9      # not in the list -> approx.
    assert ThreadFlangeParams(m="X8").validate()


def test_custom_size_and_validation():
    p, std = params_for(410)
    assert not std and (p.b, p.m, p.n, p.e, p.t) == (445, "M8", 10, 30, 10)
    assert ThreadFlangeParams(a=400, b=405, m="M8", n=10, e=30).validate()     # inner edge
    assert ThreadFlangeParams(a=400, b=455, m="M8", n=10, e=30).validate()     # outer edge
    assert ThreadFlangeParams(a=80, b=111, m="M6", n=60, e=25).validate()      # too many holes
    assert not ThreadFlangeParams(a=80, b=111, m="M6", n=4, e=25).validate()


def test_d_and_t_only_with_annotations_or_dimensions():
    p, _ = params_for(400)
    pat = develop(p)
    assert flange_thread_layout.annotations(pat, p, layout.Options()) == ([], [], [])
    for opts in (layout.Options(reference_dims=True),
                 layout.Options(reference_lines=True, piece_labels=True)):
        joined = " ".join(t[1] for t in flange_thread_layout.annotations(pat, p, opts)[2])
        assert "D 460" in joined and "T 10" in joined


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok ", name)
    print("%d tests passed" % n)
