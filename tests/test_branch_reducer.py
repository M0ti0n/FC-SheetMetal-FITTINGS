"""Run with:  python tests/test_branch_reducer.py   (no FreeCAD needed)"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hvacdev.geometry.branch_reducer import (BranchReducerParams, develop, layout,  # noqa
                                            _Model, _in_poly)
from hvacdev.geometry import branch_layout, layout as lay  # noqa

CASES = (
    {},
    dict(angle=45, h2=250, d3=120),
    dict(d1=400, d2=400),                               # straight pipe (tee)
    dict(d1=300, d2=150, angle=-20, h2=220),            # widening upwards, branch pointing down
    dict(angle=0),
)


def seg_len(s):
    """Exact length: radius x sweep for arcs, chord for lines."""
    if not s.is_arc:
        return math.dist(s.start, s.end)
    from hvacdev.geometry.arcs import circle_through
    (_, _), r = circle_through(s.start, s.mid, s.end)
    return r * abs(4 * math.atan(s.bulge()))


def chain_len(segs):
    return sum(seg_len(s) for s in segs)


def true_curve_len(p):
    m = _Model(p)
    N = 4000
    pts = [m.branch_point(2 * math.pi * i / N, m.meet(2 * math.pi * i / N)) for i in range(N + 1)]
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def test_contours_closed_lines_and_arcs():
    for kw in CASES:
        r, b = develop(BranchReducerParams(**kw))
        for pc in (r, b):
            c = pc.contour
            for s1, s2 in zip(c, c[1:] + c[:1]):
                assert math.dist(s1.end, s2.start) < 1e-6
            assert any(s.is_arc for s in c)


def test_hole_and_branch_edge_match_the_3d_intersection():
    for kw in CASES:
        p = BranchReducerParams(**kw)
        r, b = develop(p)
        true = true_curve_len(p)
        assert abs(chain_len(r.hole[0]) + chain_len(r.hole[1]) - true) < 0.02, kw
        assert abs(chain_len(b.contour[2:-1]) - true) < 0.02, kw


def test_reducer_edges_true_length():
    for kw in CASES:
        p = BranchReducerParams(**kw)
        r, _ = develop(p)
        hole = r.hole[0] + r.hole[1]
        other = [s for s in r.contour if not any(s is h for h in hole)]
        edges = chain_len([s for s in other if s.is_arc]) if p.d1 != p.d2 else \
            chain_len([s for s in other if abs(s.start[1] - s.end[1]) < 1e-9])
        assert abs(edges - math.pi * (p.d1 + p.d2)) < 1e-6, kw
        # the seam pieces on each edge add up to the slant height minus the hole span
        seam = [s for s in other if not s.is_arc and not (p.d1 == p.d2 and abs(s.start[1] - s.end[1]) < 1e-9)]
        assert len(seam) == 4


def test_reducer_seam_runs_through_the_middle_of_the_hole():
    for kw in CASES:
        r, _ = develop(BranchReducerParams(**kw))
        right, left = r.hole
        # each half starts and ends on its seam edge; the two halves mirror each other
        for half in (right, left):
            a, b = half[0].start, half[-1].end
            assert math.dist(a, b) > 1.0
        rp = [q for s in right for q in s.sample(24)]
        lp = [q for s in left for q in s.sample(24)]
        # mirror about the pattern's symmetry axis (x = 0 for a cone, x = pi*R for a pipe)
        p = BranchReducerParams(**kw)
        if p.d1 != p.d2:
            mirrored = [(-x, y) for x, y in lp]
        else:
            mirrored = [(math.pi * p.d2 - x, y) for x, y in lp]
        def d_seg(q, a, c):
            vx, vy = c[0] - a[0], c[1] - a[1]
            L2 = vx * vx + vy * vy or 1e-30
            t = max(0.0, min(1.0, ((q[0] - a[0]) * vx + (q[1] - a[1]) * vy) / L2))
            return math.dist(q, (a[0] + t * vx, a[1] + t * vy))
        for q in rp[::max(1, len(rp) // 40)]:
            assert min(d_seg(q, a, c) for a, c in zip(mirrored, mirrored[1:])) < 0.02, kw


def test_branch_seam_on_shortest_generator():
    for kw in CASES:
        p = BranchReducerParams(**kw)
        _, b = develop(p)
        assert b.seam_length <= b.longest
        m = _Model(p)
        shortest = min(p.length - m.meet(2 * math.pi * i / 720) for i in range(720))
        assert abs(b.seam_length - shortest) < 0.05, kw
    # in the diagram situation (A = 30, reducer narrowing up) the seam is on top
    _, b = develop(BranchReducerParams())
    assert abs(math.cos(b.top_beta) - 1.0) < 1e-9


def test_branch_width_and_end_square():
    p = BranchReducerParams()
    _, b = develop(p)
    x0, y0, x1, _ = b.bbox()
    assert abs((x1 - x0) - math.pi * p.d3) < 1e-6 and abs(y0) < 1e-9


def test_fold_marks_stay_out_of_the_hole():
    r, b = develop(BranchReducerParams(fold_lines=48))
    right, left = r.hole
    for half in (right, left):
        poly = [s.start for s in half] + [half[-1].end, half[0].start]
        for a, c in r.fold_marks:
            assert not _in_poly(a, poly) and not _in_poly(c, poly)
    assert len(b.fold_marks) == 2 * 48


def test_layout_no_overlap():
    r, b = develop(BranchReducerParams())
    ps = layout(r, b, 60.0)
    (_, _, _, ry1), (_, by0, _, _) = r.bbox(), b.bbox()
    assert ry1 + ps[0].offset[1] < by0 + ps[1].offset[1]


def test_validation_and_branch_must_fit():
    for bad in (dict(d1=0), dict(h2=0), dict(h2=500), dict(angle=95), dict(length=-1)):
        assert BranchReducerParams(**bad).validate()
    for bad in (dict(d3=600), dict(h2=20)):            # hole would run off the reducer
        try:
            develop(BranchReducerParams(**bad))
            assert False, bad
        except ValueError:
            pass


def test_annotations_off_by_default():
    r, b = develop(BranchReducerParams())
    for pc in (r, b):
        assert branch_layout.annotations(pc, lay.Options(), "x", 400) == ([], [], [])
        ref, dim, texts = branch_layout.annotations(
            pc, lay.Options(reference_dims=True, fold_labels=True, reference_lines=True,
                            piece_labels=True), "x", 400)
        assert ref and texts


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok ", name)
    print("%d tests passed" % n)
