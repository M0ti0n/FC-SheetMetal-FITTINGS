# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rectangular -> round (eccentric) transition - flat pattern by triangulation.

Pure Python, no FreeCAD dependency.

Geometry (neutral surface, no thickness)
----------------------------------------
Top view, origin = centre of the round, x to the right, y up:
    rectangle  x from -A to +B   ("AB side", length A + B)
               y from -F to +E   ("EF side", length E + F)
    round      diameter D, centred on the origin, height H above the rectangle

Classic triangulation: every rectangle corner is the apex of a fan towards
its quarter of the round, and each rectangle side forms one flat triangle with
the point of the round where the round is parallel to that side.
N = number of sections per quarter of the round, so the fold (bending) lines
are the 4 * (N + 1) lines from the corners to the division points.

The round edge is developed exactly (fine sub-triangulation of each oblique
cone), so the developed round edge has the true length pi * D; it is output
as circular arcs (no splines).

Seam: on the longer rectangle side (AB side if A + B >= E + F, else EF side),
along the line from the round down to the rectangle side, perpendicular to that
side - i.e. the seam foot is at x = 0 on an AB side (splitting it into A and B)
or at y = 0 on an EF side (splitting it into E and F).
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple

from . import arcs
from .marks import fold_marks_on_line

Point = Tuple[float, float]

# sides in counter-clockwise order, by the angle of their tangent point on the round
SIDE_B, SIDE_E, SIDE_A, SIDE_F = 0, 1, 2, 3          # right, top, left, bottom
SIDE_NAMES = {SIDE_B: "B", SIDE_E: "E", SIDE_A: "A", SIDE_F: "F"}

SEAM_AUTO = "Auto (longer side)"
SEAM_CHOICES = (SEAM_AUTO, "AB side at E", "AB side at F", "EF side at A", "EF side at B")
_SEAM_TO_SIDE = {"AB side at E": SIDE_E, "AB side at F": SIDE_F,
                 "EF side at A": SIDE_A, "EF side at B": SIDE_B}

SUBSTEPS_PER_QUARTER = 128      # fine triangulation of the round edge

PATTERN_COMBINED = "Combined"       # one piece, seam on the longer side
PATTERN_SHORT = "Short Side"        # short-side triangle + the two corner fans (half round)
PATTERN_LONG = "Long Side"          # flat long-side triangle only
PATTERN_MODES = (PATTERN_COMBINED, PATTERN_SHORT, PATTERN_LONG)


@dataclass
class TransitionParams:
    diameter: float = 400.0     # D
    height: float = 300.0       # H
    a: float = 300.0            # rectangle edge left of the round centre
    b: float = 200.0            # ... right
    e: float = 150.0            # ... above
    f: float = 250.0            # ... below
    sections: int = 4           # N, sections per quarter
    seam: str = SEAM_AUTO
    fold_lines: bool = True
    fold_mark_length: float = 15.0
    fold_mark_gap: float = 2.0
    arc_tol: float = 0.01

    def validate(self) -> List[str]:
        err = []
        if self.diameter <= 0:
            err.append("Diameter (D) must be greater than 0.")
        if self.height <= 0:
            err.append("Height (H) must be greater than 0.")
        for name in ("a", "b", "e", "f"):
            if getattr(self, name) <= 0:
                err.append("%s must be greater than 0 (the round centre must lie inside the "
                           "rectangle in top view)." % name.upper())
        if self.sections < 1:
            err.append("Sections per quarter (N) must be at least 1.")
        if self.seam not in SEAM_CHOICES:
            err.append("Unknown seam choice '%s'." % self.seam)
        if self.fold_mark_length <= 0 or self.fold_mark_gap < 0:
            err.append("Fold mark length must be > 0 and the edge gap >= 0.")
        return err

    def seam_side(self) -> int:
        if self.seam != SEAM_AUTO:
            return _SEAM_TO_SIDE[self.seam]
        if self.a + self.b >= self.e + self.f:        # AB side is longer (or equal)
            return SIDE_E if self.e >= self.f else SIDE_F
        return SIDE_B if self.b >= self.a else SIDE_A


@dataclass
class TransitionPattern:
    name: str
    quantity: int
    contour: List[arcs.Seg]
    outline: List[Point]                            # coarse polygon (checks / preview)
    fold_lines: List[Tuple[Point, Point]] = field(default_factory=list)   # corner -> round
    fold_marks: List[Tuple[Point, Point]] = field(default_factory=list)
    bottom_edges: List[Tuple[Point, Point, str]] = field(default_factory=list)  # straight edges + name
    seam_length: float = 0.0
    seam_side: str = ""
    overlaps: bool = False
    side_edges: List[Tuple[Point, Point, str]] = field(default_factory=list)   # seams / joints
    offset: Point = (0.0, 0.0)                      # position on the sheet (pieces side by side)
    mode: str = PATTERN_COMBINED                    # which pattern it belongs to

    def bbox(self):
        xs = [p[0] for p in self.outline]
        ys = [p[1] for p in self.outline]
        return min(xs), min(ys), max(xs), max(ys)


# ----------------------------------------------------------------- 3D model
def _corners(p):
    """Corner that FOLLOWS each side when walking counter-clockwise."""
    return {SIDE_B: (p.b, p.e, 0.0),      # after right side: top-right
            SIDE_E: (-p.a, p.e, 0.0),     # after top side: top-left
            SIDE_A: (-p.a, -p.f, 0.0),    # after left side: bottom-left
            SIDE_F: (p.b, -p.f, 0.0)}     # after bottom side: bottom-right


def _seam_foot(p, side):
    return {SIDE_B: (p.b, 0.0, 0.0), SIDE_E: (0.0, p.e, 0.0),
            SIDE_A: (-p.a, 0.0, 0.0), SIDE_F: (0.0, -p.f, 0.0)}[side]


def _round(p, theta):
    r = p.diameter / 2.0
    return (r * math.cos(theta), r * math.sin(theta), p.height)


def _d3(u, v):
    return math.sqrt((u[0] - v[0]) ** 2 + (u[1] - v[1]) ** 2 + (u[2] - v[2]) ** 2)


# ------------------------------------------------------------ 2D unfolding
def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _third_point(P, Q, dP, dQ, want_sign, orient):
    """Point X with |PX| = dP, |QX| = dQ; of the two solutions take the one
    for which orient(X) has the sign `want_sign`."""
    dx, dy = Q[0] - P[0], Q[1] - P[1]
    d = math.hypot(dx, dy)
    a = (dP * dP - dQ * dQ + d * d) / (2 * d)
    h = math.sqrt(max(dP * dP - a * a, 0.0))
    bx, by = P[0] + a * dx / d, P[1] + a * dy / d
    c1 = (bx - h * dy / d, by + h * dx / d)
    c2 = (bx + h * dy / d, by - h * dx / d)
    return c1 if orient(c1) * want_sign >= orient(c2) * want_sign else c2


def develop(p: TransitionParams) -> TransitionPattern:
    errors = p.validate()
    if errors:
        raise ValueError("\n".join(errors))

    N = p.sections
    sub = max(1, math.ceil(SUBSTEPS_PER_QUARTER / N))     # sub-steps per section
    steps = N * sub                                       # per quarter
    seam = p.seam_side()
    corners = _corners(p)
    theta0 = seam * math.pi / 2

    S3 = _seam_foot(p, seam)
    T3 = _round(p, theta0)
    b3, t3 = S3, T3
    b2 = (0.0, 0.0)
    t2 = (0.0, _d3(S3, T3))

    bottom2 = [b2]                    # developed rectangle-edge points (S, 4 corners, S')
    top2 = [t2]                       # developed round edge (dense)
    fold_lines = []

    def new_bottom(nb3):
        nonlocal b2, b3
        nb2 = _third_point(b2, t2, _d3(b3, nb3), _d3(t3, nb3), +1,
                           lambda X: _cross(b2, X, t2))
        b2, b3 = nb2, nb3
        bottom2.append(nb2)

    # fan triangle (b, t_old, t_new) must satisfy orient(b, t_new, t_old) > 0
    def new_top_fan(nt3):
        nonlocal t2, t3
        nt2 = _third_point(b2, t2, _d3(b3, nt3), _d3(t3, nt3), +1,
                           lambda X: _cross(b2, X, t2))
        t2, t3 = nt2, nt3
        top2.append(nt2)

    fan_ranges = []                   # (start index in top2, end index) per corner
    for j in range(4):
        side = (seam + j) % 4
        corner = corners[side]
        new_bottom(corner)            # flat triangle of this side (half side for j = 0)
        start = len(top2) - 1
        fold_lines.append((b2, t2))
        for k in range(1, steps + 1):
            new_top_fan(_round(p, theta0 + (j * steps + k) * (math.pi / 2) / steps))
            if k % sub == 0:
                fold_lines.append((b2, t2))
        fan_ranges.append((start, len(top2) - 1))
    new_bottom(S3)                    # second half of the seam side

    # ---- contour: rectangle edge (lines), seam, round edge (arcs), seam
    contour = []
    bottom_edges = []
    names = []
    for j in range(5):
        if j == 0:
            names.append(SIDE_NAMES[seam] + "-side 1/2")
        elif j == 4:
            names.append(SIDE_NAMES[seam] + "-side 2/2")
        else:
            names.append(SIDE_NAMES[(seam + j) % 4] + "-side")
    for j in range(5):
        contour.append(arcs.Seg(bottom2[j], bottom2[j + 1]))
        bottom_edges.append((bottom2[j], bottom2[j + 1], names[j]))
    contour.append(arcs.Seg(bottom2[-1], top2[-1]))                 # right seam
    round_segs = []
    for i0, i1 in fan_ranges:                                       # arcs per corner fan
        round_segs += arcs.fit_points(top2[i0:i1 + 1], p.arc_tol)
    contour += [sg.reversed() for sg in reversed(round_segs)]
    contour.append(arcs.Seg(top2[0], bottom2[0]))                   # left seam

    outline = bottom2 + list(reversed(top2[::max(1, sub // 4)] + [top2[-1]])) + [bottom2[0]]

    pat = TransitionPattern("Transition", 1, contour, outline,
                            fold_lines=fold_lines, bottom_edges=bottom_edges,
                            seam_length=_d3(S3, T3), seam_side=SIDE_NAMES[seam],
                            side_edges=[(top2[0], bottom2[0], "SEAM")])
    if p.fold_lines:
        for a, b in fold_lines:
            # all folds of a fan meet in the rectangle corner, so marks only at the round edge
            pat.fold_marks += fold_marks_on_line(a, b, p.fold_mark_length, p.fold_mark_gap, ends="end")
    pat.overlaps = _self_intersects(bottom2 + list(reversed(top2)))
    return pat


# ------------------------------------------------------------ split pieces
class _Strip:
    """Unfolds a strip of triangles between the rectangle edge (bottom chain)
    and the round edge (top chain), starting from the edge b3 - t3."""

    def __init__(self, b3, t3):
        self.b3, self.t3 = b3, t3
        self.b2, self.t2 = (0.0, 0.0), (0.0, _d3(b3, t3))
        self.bottom2, self.top2 = [self.b2], [self.t2]

    def _place(self, n3):
        b2, t2 = self.b2, self.t2
        return _third_point(b2, t2, _d3(self.b3, n3), _d3(self.t3, n3), +1,
                            lambda X: _cross(b2, X, t2))

    def bottom(self, n3):
        self.b2, self.b3 = self._place(n3), n3
        self.bottom2.append(self.b2)

    def top(self, n3):
        self.t2, self.t3 = self._place(n3), n3
        self.top2.append(self.t2)


def _rotate_to_base(pat):
    """Turn a piece so its rectangle edge lies on the x axis, starting at 0."""
    (x0, y0), (x1, y1) = pat.bottom_edges[0][0], pat.bottom_edges[-1][1]
    ang = -math.atan2(y1 - y0, x1 - x0)
    c, sn = math.cos(ang), math.sin(ang)

    def tr(q):
        x, y = q[0] - x0, q[1] - y0
        return (x * c - y * sn, x * sn + y * c)

    pat.contour = [sg.mapped(tr) for sg in pat.contour]
    pat.outline = [tr(q) for q in pat.outline]
    pat.fold_lines = [(tr(a), tr(b)) for a, b in pat.fold_lines]
    pat.fold_marks = [(tr(a), tr(b)) for a, b in pat.fold_marks]
    pat.bottom_edges = [(tr(a), tr(b), n) for a, b, n in pat.bottom_edges]
    pat.side_edges = [(tr(a), tr(b), n) for a, b, n in pat.side_edges]
    return pat


def _finish_piece(p, strip, name, qty, fold_lines, fan_ranges, bottom_names):
    b2, t2 = strip.bottom2, strip.top2
    contour, bottom_edges = [], []
    for j in range(len(b2) - 1):
        contour.append(arcs.Seg(b2[j], b2[j + 1]))
        bottom_edges.append((b2[j], b2[j + 1], bottom_names[j]))
    contour.append(arcs.Seg(b2[-1], t2[-1]))
    round_segs = []
    for i0, i1 in fan_ranges:
        round_segs += arcs.fit_points(t2[i0:i1 + 1], p.arc_tol)
    contour += [sg.reversed() for sg in reversed(round_segs)]
    contour.append(arcs.Seg(t2[0], b2[0]))
    outline = b2 + list(reversed(t2)) + [b2[0]]
    pat = TransitionPattern(name, qty, contour, outline, fold_lines=fold_lines,
                            bottom_edges=bottom_edges,
                            side_edges=[(b2[-1], t2[-1], "JOINT"), (t2[0], b2[0], "JOINT")])
    if p.fold_lines:
        for a, b in fold_lines:
            pat.fold_marks += fold_marks_on_line(a, b, p.fold_mark_length, p.fold_mark_gap, ends="end")
    pat.overlaps = _self_intersects(b2 + list(reversed(t2)))
    return _rotate_to_base(pat)


def _short_piece(p, side, qty):
    """Triangle on `side` + the fans of its two corners (a half round)."""
    N = p.sections
    sub = max(1, math.ceil(SUBSTEPS_PER_QUARTER / N))
    steps = N * sub
    corners = _corners(p)
    prev_c, next_c = corners[(side - 1) % 4], corners[side]
    th = side * math.pi / 2
    strip = _Strip(prev_c, _round(p, th - math.pi / 2))
    folds, fans = [], []
    for k in range(1, steps + 1):                      # fan of the first corner
        strip.top(_round(p, th - math.pi / 2 + k * (math.pi / 2) / steps))
        if k % sub == 0:                               # k = steps: bend into the triangle
            folds.append((strip.b2, strip.t2))
    fans.append((0, len(strip.top2) - 1))
    strip.bottom(next_c)                               # the short-side triangle
    folds.append((strip.b2, strip.t2))                 # bend triangle -> second fan
    start = len(strip.top2) - 1
    for k in range(1, steps + 1):                      # fan of the second corner
        strip.top(_round(p, th + k * (math.pi / 2) / steps))
        if k % sub == 0 and k < steps:                 # last line is the cut edge
            folds.append((strip.b2, strip.t2))
    fans.append((start, len(strip.top2) - 1))
    name = "Short side %s" % SIDE_NAMES[side] if qty == 1 else "Short side"
    return _finish_piece(p, strip, name, qty, folds, fans, ["%s-side" % SIDE_NAMES[side]])


def _long_piece(p, side, qty):
    """Flat triangle on `side`, no round parts."""
    corners = _corners(p)
    prev_c, next_c = corners[(side - 1) % 4], corners[side]
    strip = _Strip(prev_c, _round(p, side * math.pi / 2))
    strip.bottom(next_c)
    name = "Long side %s" % SIDE_NAMES[side] if qty == 1 else "Long side"
    return _finish_piece(p, strip, name, qty, [], [], ["%s-side" % SIDE_NAMES[side]])


def short_and_long_sides(p):
    """(short sides, long sides) as side ids; AB sides (E, F) count as long when A + B >= E + F."""
    if p.a + p.b >= p.e + p.f:
        return (SIDE_A, SIDE_B), (SIDE_E, SIDE_F)
    return (SIDE_E, SIDE_F), (SIDE_A, SIDE_B)


def _same(p, s1, s2):
    """Pieces on opposite sides are mirror images (= the same part) when the
    rectangle is centred across them."""
    if {s1, s2} == {SIDE_A, SIDE_B}:
        return abs(p.a - p.b) < 1e-9
    return abs(p.e - p.f) < 1e-9


def develop_pieces(p: TransitionParams, mode: str = PATTERN_COMBINED) -> List[TransitionPattern]:
    """Flat pattern(s) for the chosen preview mode, laid out side by side."""
    errors = p.validate()
    if errors:
        raise ValueError("\n".join(errors))
    if mode == PATTERN_COMBINED:
        return [develop(p)]
    short, long_ = short_and_long_sides(p)
    sides = short if mode == PATTERN_SHORT else long_
    make = _short_piece if mode == PATTERN_SHORT else _long_piece
    if _same(p, *sides):
        pieces = [make(p, sides[0], 2)]
    else:
        pieces = [make(p, s, 1) for s in sides]
    gap = max(50.0, 0.12 * p.diameter)
    x = 0.0
    for pc in pieces:
        x0, _, x1, _ = pc.bbox()
        pc.offset = (x - x0, 0.0)
        x += (x1 - x0) + gap
    return pieces


def develop_selection(p: TransitionParams, combined=True, short=False, long_=False):
    """All pieces for the ticked patterns. Each pattern gets its own row
    (Combined at the bottom, then Short Side, then Long Side above it)."""
    rows = [m for m, on in ((PATTERN_COMBINED, combined), (PATTERN_SHORT, short),
                            (PATTERN_LONG, long_)) if on]
    out = []
    gap = max(50.0, 0.12 * p.diameter)
    y = 0.0
    for mode in rows:
        pieces = develop_pieces(p, mode)
        y_min = min(pc.bbox()[1] for pc in pieces)
        y_max = max(pc.bbox()[3] for pc in pieces)
        for pc in pieces:
            pc.offset = (pc.offset[0], y - y_min)
            pc.mode = mode
        out += pieces
        y += (y_max - y_min) + gap
    return out


def _self_intersects(poly: List[Point]) -> bool:
    """True if the closed polygon crosses itself (pattern would overlap)."""
    pts = poly[::max(1, len(poly) // 400)] if len(poly) > 800 else poly
    n = len(pts)
    segs = [(pts[i], pts[(i + 1) % n]) for i in range(n)]

    def inter(p1, p2, p3, p4):
        d1, d2 = _cross(p3, p4, p1), _cross(p3, p4, p2)
        d3, d4 = _cross(p1, p2, p3), _cross(p1, p2, p4)
        return (d1 * d2 < 0) and (d3 * d4 < 0)

    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if inter(*segs[i], *segs[j]):
                return True
    return False


def summary(p: TransitionParams) -> dict:
    pat = develop(p)
    return {"seam_side": pat.seam_side, "seam_length": pat.seam_length,
            "fold_lines": len(pat.fold_lines), "overlaps": pat.overlaps}
