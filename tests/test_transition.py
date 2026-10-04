"""Run with:  python tests/test_transition.py   (no FreeCAD needed)"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hvacdev.geometry.transition import (TransitionParams, develop, SEAM_CHOICES,  # noqa
                                         _corners, _round)
from hvacdev.geometry import transition_layout, layout  # noqa

CASES = (
    {},
    dict(a=200, b=200, e=200, f=200),
    dict(a=150, b=500, e=100, f=120, diameter=315, height=200, sections=3),
    dict(a=400, b=100, e=500, f=150, sections=6),
    dict(a=120, b=120, e=90, f=90, diameter=250, height=150, sections=1),
)


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def test_rectangle_edges_keep_true_lengths():
    for kw in CASES:
        p = TransitionParams(**kw)
        t = develop(p)
        total = sum(math.dist(a, b) for a, b, _ in t.bottom_edges)
        assert approx(total, 2 * (p.a + p.b + p.e + p.f))


def test_round_edge_has_true_length():
    for kw in CASES:
        p = TransitionParams(**kw)
        t = develop(p)
        length = 0.0
        for sg in t.contour[6:-1]:              # the arc chain of the round edge
            pts = sg.sample(32)
            length += sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        assert abs(length - math.pi * p.diameter) < 0.05, (kw, length)


def test_fold_lines_match_3d_and_count():
    for kw in CASES:
        p = TransitionParams(**kw)
        t = develop(p)
        assert len(t.fold_lines) == 4 * (p.sections + 1)
        # every fold line = true 3D distance corner -> division point on the round
        seam = p.seam_side()
        corners = _corners(p)
        i = 0
        for j in range(4):
            c = corners[(seam + j) % 4]
            for k in range(p.sections + 1):
                th = seam * math.pi / 2 + (j * p.sections + k) * (math.pi / 2) / p.sections
                a, b = t.fold_lines[i]
                assert abs(math.dist(a, b) - math.dist(c, _round(p, th))) < 1e-6
                i += 1


def test_seam_on_longer_side_and_both_seam_edges_equal():
    # AB longer -> seam on an AB side (E or F)
    assert develop(TransitionParams(a=300, b=200, e=150, f=250)).seam_side in ("E", "F")
    # EF longer -> seam on an EF side (A or B)
    assert develop(TransitionParams(a=100, b=150, e=300, f=300)).seam_side in ("A", "B")
    for kw in CASES:
        t = develop(TransitionParams(**kw))
        right, left = t.contour[5], t.contour[-1]
        assert approx(math.dist(right.start, right.end), math.dist(left.start, left.end))
        assert approx(math.dist(left.start, left.end), t.seam_length)


def test_manual_seam_choice():
    for choice, side in zip(SEAM_CHOICES[1:], ("E", "F", "A", "B")):
        assert develop(TransitionParams(seam=choice)).seam_side == side


def test_contour_closed_lines_and_arcs_only():
    for kw in CASES:
        t = develop(TransitionParams(**kw))
        c = t.contour
        for s1, s2 in zip(c, c[1:] + c[:1]):
            assert math.dist(s1.end, s2.start) < 1e-9
        assert any(sg.is_arc for sg in c)
        assert not t.overlaps


def test_fold_marks_at_round_edge():
    p = TransitionParams()
    t = develop(p)
    assert len(t.fold_marks) == len(t.fold_lines)
    for (a, b), (m0, m1) in zip(t.fold_lines, t.fold_marks):
        assert abs(math.dist(m1, b) - 2.0) < 1e-9
        assert abs(math.dist(m0, m1) - 15.0) < 1e-9


def test_validation():
    for bad in (dict(diameter=0), dict(height=0), dict(a=0), dict(f=-5), dict(sections=0)):
        assert TransitionParams(**bad).validate()
    assert not TransitionParams().validate()


def test_annotations_off_by_default():
    t = develop(TransitionParams())
    ref, dim, texts = transition_layout.annotations(t, layout.Options(), "x", 400)
    assert not ref and not dim and not texts
    ref, dim, texts = transition_layout.annotations(
        t, layout.Options(reference_dims=True, fold_labels=True, reference_lines=True, piece_labels=True),
        "x", 400)
    assert len(ref) == len(t.fold_lines) and texts


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok ", name)
    print("%d tests passed" % n)
