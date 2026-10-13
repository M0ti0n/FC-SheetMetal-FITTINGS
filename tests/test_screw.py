"""Run with:  python tests/test_screw.py   (no FreeCAD needed)"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hvacdev.geometry.screw import ScrewParams, calculate, develop  # noqa
from hvacdev.geometry import screw_layout, layout  # noqa
from hvacdev.geometry.arcs import circle_through  # noqa


def excel(D, d, P):
    """The KALKULATOR formula from the KOSOVNICA workbook (with its pi approximations)."""
    li = (d * d * 9.869 + P * P) ** .5
    lo = (D * D * 9.869 + P * P) ** .5
    h = (D - d) / 2
    ri = h * li / (lo - li)
    return ri, ri + h, 180 * li / (ri * 3.14)


def test_matches_the_excel_calculator():
    for D, d, P in ((315, 101.6, 300), (200, 60, 200), (400, 114, 400), (500, 168, 250)):
        r = calculate(ScrewParams(od=D, id=d, pitch=P))
        ri, ro, ang = excel(D, d, P)
        assert abs(r.ri - ri) < 0.01 and abs(r.ro - ro) < 0.01
        assert 0.1 < ang - r.calc_angle < 0.2          # Excel uses pi = 3.14 in the angle


def test_edges_have_the_helix_lengths():
    r = calculate(ScrewParams())
    t = math.radians(r.calc_angle)
    assert abs(r.ri * t - math.hypot(math.pi * 101.6, 300)) < 1e-9
    assert abs(r.ro * t - math.hypot(math.pi * 315, 300)) < 1e-9


def test_extension_leaves_6mm_at_the_inner_edge():
    for gap in (6, 3, 10):
        b = develop(ScrewParams(gap=gap))
        r = b.result
        cut_a_inner = b.contour[-1].start          # inner point of the right cut edge
        cut_b_inner = [s for s in b.contour if not s.is_arc][0].end   # inner point of the left cut edge
        assert abs(math.dist(cut_a_inner, cut_b_inner) - gap) < 1e-9
        assert abs(r.blank_angle + r.gap_angle - 360) < 1e-9
        assert r.blank_angle > r.calc_angle and abs(r.extension - (r.blank_angle - r.calc_angle)) < 1e-9
    r = calculate(ScrewParams())
    assert abs(r.blank_angle - 355.615) < 0.01 and abs(r.extension - 35.556) < 0.01


def test_pieces():
    assert calculate(ScrewParams(length=1000, pitch=300)).pieces == 4
    assert calculate(ScrewParams(length=900, pitch=300)).pieces == 3
    assert calculate(ScrewParams(length=100, pitch=300)).pieces == 1


def test_contour_closed_arcs_and_radii():
    b = develop(ScrewParams())
    c = b.contour
    assert all(math.dist(s1.end, s2.start) < 1e-9 for s1, s2 in zip(c, c[1:] + c[:1]))
    lines = [s for s in c if not s.is_arc]
    assert len(lines) == 2
    for s in c:
        if s.is_arc:
            (cc), rr = circle_through(s.start, s.mid, s.end)
            assert math.dist(cc, b.centre) < 1e-6
            assert min(abs(rr - b.result.ri), abs(rr - b.result.ro)) < 1e-6
    x0, y0, x1, y1 = b.bbox()
    assert abs(x0) < 1e-9 and abs(y0) < 1e-9


def test_validation_and_tiny_gap_case():
    for bad in (dict(od=100, id=100), dict(id=0), dict(pitch=0), dict(length=0), dict(gap=-1)):
        try:
            calculate(ScrewParams(**bad))
            assert False, bad
        except ValueError:
            pass
    # very small pitch: the calculated angle approaches 360, the gap cannot be 6 mm
    r = calculate(ScrewParams(od=315, id=101.6, pitch=5, gap=6))
    assert r.warnings and abs(r.blank_angle - r.calc_angle) < 1e-9


def test_annotations_off_by_default():
    b = develop(ScrewParams())
    p = ScrewParams()
    assert screw_layout.annotations(b, p, layout.Options()) == ([], [], [])
    _, _, texts = screw_layout.annotations(b, p, layout.Options(reference_dims=True, piece_labels=True,
                                                                reference_lines=True))
    joined = " ".join(t[1] for t in texts)
    assert "x4" in joined and "355.6" in joined


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok ", name)
    print("%d tests passed" % n)
