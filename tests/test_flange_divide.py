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
        assert sum(q * h for _, q, h in hole_counts(n)) == n


def test_all_sections_are_120_deg():
    for n in range(3, 40):
        assert all(abs(sec.span - 120.0) < 1e-9 for sec in plan(n))
        cuts = cut_angles(n)
        steps = [(b - a) % 360 for a, b in zip(cuts, cuts[1:] + cuts[:1])]
        assert all(abs(x - 120.0) < 1e-9 for x in steps)


def test_first_cut_midway_between_holes():
    for n in range(3, 40):
        step = 360.0 / n
        holes = [90.0 + step * k for k in range(n)]
        cuts = cut_angles(n)
        assert abs(min(ang_dist(cuts[0], h) for h in holes) - step / 2) < 1e-9
        if n % 3 == 0:                      # then every cut is midway
            for c in cuts:
                assert abs(min(ang_dist(c, h) for h in holes) - step / 2) < 1e-9


def test_sections_next_to_the_first_cut_are_mirror_images():
    for n in (4, 5, 7, 8, 10, 11, 16, 20):
        step = 360.0 / n
        c0 = cut_angles(n)[0]
        holes = [90.0 + step * k for k in range(n)]
        # holes of the section after the first cut, measured from the cut ...
        after = sorted(round((h - c0) % 360, 9) for h in holes if 0 < (h - c0) % 360 < 120)
        # ... and of the section before it, measured backwards from the cut
        before = sorted(round((c0 - h) % 360, 9) for h in holes if 0 < (c0 - h) % 360 < 120)
        assert after == before, n
        # section B is symmetric about its own middle (c0 + 180)
        b_rel = sorted(round(((h - (c0 + 180)) + 180) % 360 - 180, 9) for h in holes
                       if 120 < (h - c0) % 360 < 240)
        assert b_rel == sorted(-x for x in b_rel), n


def test_standard_sizes_cuts_clear_slots_and_holes():
    from hvacdev.geometry.flange_table import SIZES as S1
    from hvacdev.geometry.flange_thread_table import SIZES as S2
    from hvacdev.geometry.flange_divide import cut_clearance
    for A, B, M, N, E, T in S1:
        if can_divide(A, N):
            assert cut_clearance(N, B, 12.5 + M / 2) > 1.0, A
    for A, B, M, N, E, T in S2:
        if can_divide(A, N):
            assert cut_clearance(N, B, tg.thread_diameter(M) / 2) > 1.0, A


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
            # the 120 deg sector outline itself is symmetric about the vertical middle line
            xs = sorted(round(q[0] - mid_x, 6) for s in sector for q in (s.start, s.end))
            assert all(abs(u + v) < 1e-6 for u, v in zip(xs, reversed(xs)))
            assert abs(pc.span - 120.0) < 1e-9


def test_thread_flange_sections_marks():
    p, _ = tg.params_for(400)                     # N 10
    pat = tg.develop(p)
    pieces = make_pieces(pat.centre, p.a / 2, p.d / 2, p.n, p.start_angle,
                         lambda k: [], lambda k: pat.marks[2 * k: 2 * k + 2],
                         lambda k: pat.hole_centres[k])
    assert [(pc.name, pc.quantity, pc.holes, len(pc.marks), round(pc.span, 9)) for pc in pieces] == \
        [("Section A", 2, 3, 6, 120.0), ("Section B", 1, 4, 8, 120.0)]


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok ", name)
    print("%d tests passed" % n)
