"""Run with:  python tests/test_flange_divide.py   (no FreeCAD needed)"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hvacdev.geometry.flange_divide import (plan, cut_angles, hole_counts, can_divide,  # noqa
                                           sector_contour, make_pieces)
from hvacdev.geometry import flange as fg, flange_thread as tg  # noqa


def ang_dist(a, b):
    d = (a - b) % 360.0
    return min(d, 360.0 - d)


def test_counts_follow_the_rules():
    assert hole_counts(6) == [("Section", 3, 2)]
    assert hole_counts(12) == [("Section", 3, 4)]
    assert hole_counts(8) == [("Section A", 2, 3), ("Section B", 1, 2)]
    assert hole_counts(10) == [("Section A", 2, 3), ("Section B", 1, 4)]
    assert hole_counts(16) == [("Section A", 2, 5), ("Section B", 1, 6)]
    for n in range(3, 40):
        total = sum(q * h for _, q, h in hole_counts(n))
        assert total == n


def test_spans():
    s = {p.name: round(p.span, 6) for p in plan(10)}
    assert s == {"Section A": 108.0, "Section B": 144.0}
    s = {p.name: round(p.span, 6) for p in plan(8)}
    assert s == {"Section A": 135.0, "Section B": 90.0}
    assert [round(p.span, 6) for p in plan(6)] == [120.0]


def test_cuts_always_midway_between_holes():
    for n in range(3, 40):
        step = 360.0 / n
        holes = [90.0 + step * k for k in range(n)]
        cuts = cut_angles(n)
        assert len(cuts) == 3
        for c in cuts:
            nearest = min(ang_dist(c, h) for h in holes)
            assert abs(nearest - step / 2) < 1e-9, (n, c)
        # the three sections together are the full circle
        steps = sorted(((b - a) % 360 for a, b in zip(cuts, cuts[1:] + cuts[:1])))
        assert abs(sum(steps) - 360) < 1e-9
        if n % 3 == 0:
            assert all(abs(x - 120) < 1e-9 for x in steps)


def test_section_b_at_the_bottom():
    for n in (6, 8, 10, 16):
        b = [sec for sec in plan(n) if sec.name in ("Section B", "Section")][0]
        assert ang_dist(b.mid, 270.0) <= 360.0 / n / 2 + 1e-9


def test_a80_and_a100_not_divided():
    assert not can_divide(80, 4) and not can_divide(100, 4)
    assert can_divide(120, 6)


def test_sector_contour_closed():
    c = sector_contour((0, 0), 100, 130, 10, 154)
    assert all(math.dist(a.end, b.start) < 1e-9 for a, b in zip(c, c[1:] + c[:1]))
    assert all(abs(math.dist(s.mid, (0, 0)) - r) < 1e-9 for s, r in ((c[0], 130), (c[-2], 100)))


def _slot_flange_pieces(a):
    p, _ = fg.params_for(a)
    pat = fg.develop(p)
    return p, pat, make_pieces(pat.centre, p.a / 2, p.d / 2, p.n, p.start_angle,
                               lambda k: [pat.slots[k]], lambda k: [],
                               lambda k: pat.hole_centres[3 * k + 1])


def test_slot_flange_sections_contain_their_slots_and_point_up():
    for a in (120, 400, 820):                     # N 6, 10, 16
        p, pat, pieces = _slot_flange_pieces(a)
        assert sum(pc.quantity * pc.holes for pc in pieces) == p.n
        for pc in pieces:
            assert len(pc.contours) == 1 + pc.holes
            sector = pc.contours[0]
            x0, y0, x1, y1 = pc.bbox()
            assert abs(x0) < 1e-9 and abs(y0) < 1e-9
            # every slot lies inside the sector's angular range (no cut through a slot)
            mid_x = (x0 + x1) / 2
            for slot in pc.contours[1:]:
                for s in slot:
                    for q in s.sample(8):
                        assert x0 - 1e-6 <= q[0] <= x1 + 1e-6 and y0 - 1e-6 <= q[1] <= y1 + 1e-6
            # symmetric about the vertical middle line
            xs = sorted(round(q[0] - mid_x, 6) for s in sector for q in (s.start, s.end))
            assert all(abs(u + v) < 1e-6 for u, v in zip(xs, reversed(xs)))


def test_thread_flange_sections_marks():
    p, _ = tg.params_for(400)                     # N 10
    pat = tg.develop(p)
    pieces = make_pieces(pat.centre, p.a / 2, p.d / 2, p.n, p.start_angle,
                         lambda k: [], lambda k: pat.marks[2 * k: 2 * k + 2],
                         lambda k: pat.hole_centres[k])
    assert [(pc.name, pc.quantity, pc.holes, len(pc.marks)) for pc in pieces] == \
        [("Section A", 2, 3, 6), ("Section B", 1, 4, 8)]


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok ", name)
    print("%d tests passed" % n)
