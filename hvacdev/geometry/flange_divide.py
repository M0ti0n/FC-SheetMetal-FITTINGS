# SPDX-License-Identifier: LGPL-2.1-or-later
"""Divide a ring flange into 3 sections of 120 deg (shared by both flange tools).

Rules
-----
* The FIRST cut is radial and lies exactly in the middle between two
  neighbouring holes / slots (next to the top hole).
* The other two cuts follow at exactly +120 and +240 deg, wherever the
  holes are - all three sections are 120 deg.
* N divisible by 3: every cut is midway between holes and the three
  sections are identical -> one drawing x3.
* Otherwise the hole pattern is symmetric about the first cut, so the two
  sections touching it are mirror images of each other (the same flat
  part) -> Section A x2; the section opposite the first cut -> Section B x1.
* Flanges with A <= 100 mm are not divided.
* For custom values a 120 / 240 deg cut could hit a slot or hole: that is
  reported by cut_clearance() (all table sizes are clear).
"""

import math
from dataclasses import dataclass, field
from typing import Callable, List, Tuple

from . import arcs

Point = Tuple[float, float]
MIN_DIVIDE_A = 100.0        # A80 and A100 are never divided


def can_divide(a: float, n: int) -> bool:
    return a > MIN_DIVIDE_A + 1e-9 and n >= 3


def first_cut(n: int, start_angle: float = 90.0) -> float:
    """Angle [deg] of the first cut: midway between the top hole and the next one."""
    return start_angle + 180.0 / n


def _holes_between(n, start_angle, a0, a1):
    step = 360.0 / n
    out = []
    for k in range(n):
        phi = start_angle + step * k
        rel = (phi - a0) % 360.0
        if 1e-9 < rel < (a1 - a0) - 1e-9:
            out.append(k)
    return out


def hole_counts(n: int):
    """[(name, quantity, holes per section)] for the unique sections."""
    secs = plan(n)
    return [(sec.name, sec.quantity, len(sec.holes)) for sec in secs]


@dataclass
class SectionPlan:
    name: str
    quantity: int
    holes: List[int]          # hole indices whose centre lies in this section
    a0: float                 # start cut angle [deg]
    a1: float                 # end cut angle [deg] (a1 = a0 + 120)

    @property
    def span(self):
        return self.a1 - self.a0

    @property
    def mid(self):
        return 0.5 * (self.a0 + self.a1)


def plan(n: int, start_angle: float = 90.0) -> List[SectionPlan]:
    """Unique sections: [Section x3] or [Section A x2, Section B x1].
    Section A starts at the first cut, B is the one opposite the first cut."""
    c0 = first_cut(n, start_angle)
    if n % 3 == 0:
        return [SectionPlan("Section", 3, _holes_between(n, start_angle, c0, c0 + 120.0), c0, c0 + 120.0)]
    return [SectionPlan("Section A", 2, _holes_between(n, start_angle, c0, c0 + 120.0), c0, c0 + 120.0),
            SectionPlan("Section B", 1, _holes_between(n, start_angle, c0 + 120.0, c0 + 240.0),
                        c0 + 120.0, c0 + 240.0)]


def cut_angles(n: int, start_angle: float = 90.0) -> List[float]:
    """The three cut angles [deg] on the whole flange."""
    c0 = first_cut(n, start_angle)
    return [c0 % 360.0, (c0 + 120.0) % 360.0, (c0 + 240.0) % 360.0]


def cut_clearance(n: int, b: float, half_extent: float, start_angle: float = 90.0) -> float:
    """Smallest distance [mm, along the B circle] between a cut and the edge of
    a slot / hole; half_extent = half the slot length incl. end caps, or the
    hole radius. Negative = a cut goes through a slot / hole."""
    step = 360.0 / n
    rb = b / 2.0
    worst = float("inf")
    for c in cut_angles(n, start_angle):
        for k in range(n):
            d = abs(((c - (start_angle + step * k)) + 180.0) % 360.0 - 180.0)
            worst = min(worst, math.radians(d) * rb - half_extent)
    return worst


def sector_contour(c: Point, r_in: float, r_out: float, a0: float, a1: float) -> List[arcs.Seg]:
    """Closed ring sector a0..a1 [deg]: outer arc, cut, inner arc, cut (arcs <= 90 deg)."""
    cx, cy = c

    def P(r, deg):
        a = math.radians(deg)
        return (cx + r * math.cos(a), cy + r * math.sin(a))

    k = max(1, math.ceil((a1 - a0) / 90.0))
    outer = [arcs.Seg(P(r_out, a0 + (a1 - a0) * i / k), P(r_out, a0 + (a1 - a0) * (i + 1) / k),
                      P(r_out, a0 + (a1 - a0) * (i + 0.5) / k)) for i in range(k)]
    inner = [arcs.Seg(P(r_in, a1 - (a1 - a0) * i / k), P(r_in, a1 - (a1 - a0) * (i + 1) / k),
                      P(r_in, a1 - (a1 - a0) * (i + 0.5) / k)) for i in range(k)]
    return outer + [arcs.Seg(P(r_out, a1), P(r_in, a1))] + inner + [arcs.Seg(P(r_in, a0), P(r_out, a0))]


@dataclass
class SectionPiece:
    name: str
    quantity: int
    span: float                                   # [deg]
    holes: int
    contours: List[List[arcs.Seg]]                # sector + slots (local coordinates)
    marks: List[Tuple[Point, Point]] = field(default_factory=list)
    hole_centres: List[Point] = field(default_factory=list)
    label_pos: Point = (0.0, 0.0)
    offset: Point = (0.0, 0.0)

    def bbox(self):
        pts = [q for c in self.contours for s in c for q in s.sample(12)]
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        return min(xs), min(ys), max(xs), max(ys)


def make_pieces(c: Point, r_in: float, r_out: float, n: int, start_angle: float,
                hole_contours: Callable[[int], List[List[arcs.Seg]]],
                hole_marks: Callable[[int], List[Tuple[Point, Point]]],
                hole_centre: Callable[[int], Point]) -> List[SectionPiece]:
    """Section drawings, each turned so its middle points up, origin at its own
    bounding-box corner (0, 0)."""
    pieces = []
    for sec in plan(n, start_angle):
        rot = math.radians(90.0 - sec.mid)
        cr, sr = math.cos(rot), math.sin(rot)

        def tr(q, cr=cr, sr=sr):
            x, y = q[0] - c[0], q[1] - c[1]
            return (x * cr - y * sr, x * sr + y * cr)

        contours = [sector_contour(c, r_in, r_out, sec.a0, sec.a1)]
        marks, centres = [], []
        for k in sec.holes:
            contours += hole_contours(k)
            marks += hole_marks(k)
            centres.append(hole_centre(k))
        pc = SectionPiece(sec.name, sec.quantity, sec.span, len(sec.holes),
                          [[s.mapped(tr) for s in cn] for cn in contours],
                          [(tr(a), tr(b)) for a, b in marks], [tr(q) for q in centres])
        x0, y0, _, _ = pc.bbox()

        def sh(q, x0=x0, y0=y0):
            return (q[0] - x0, q[1] - y0)

        pc.contours = [[s.mapped(sh) for s in cn] for cn in pc.contours]
        pc.marks = [(sh(a), sh(b)) for a, b in pc.marks]
        pc.hole_centres = [sh(q) for q in pc.hole_centres]
        pc.label_pos = sh((0.0, r_in - (r_out - r_in) * 0.9))     # inside the curve
        pieces.append(pc)
    return pieces


def layout_rows(whole_size: float, pieces: List[SectionPiece], show_whole: bool, gap: float):
    """Whole flange in the bottom row (0..whole_size), sections in a row above it.
    Returns (offset_of_whole, pieces with offsets set)."""
    y = whole_size + gap if show_whole else 0.0
    x = 0.0
    for pc in pieces:
        x0, y0, x1, y1 = pc.bbox()
        pc.offset = (x - x0, y - y0)
        x += (x1 - x0) + gap
    return (0.0, 0.0), pieces
