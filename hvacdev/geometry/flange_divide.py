# SPDX-License-Identifier: LGPL-2.1-or-later
"""Divide a ring flange into 3 sections (shared by both flange tools).

Rules
-----
* Every cut is radial and lies exactly in the middle between two
  neighbouring holes / slots - never through one.
* N divisible by 3: three equal 120 deg sections -> one drawing x3.
* Otherwise the holes are split as evenly as possible (N = 3q + r):
      r = 1 -> q, q, q+1 holes      r = 2 -> q+1, q+1, q holes
  The two sections with the same hole count are identical (symmetric)
  -> section A x2, the third one -> section B x1.
* Flanges with A <= 100 mm are not divided.
"""

import math
from dataclasses import dataclass, field
from typing import Callable, List, Tuple

from . import arcs

Point = Tuple[float, float]
MIN_DIVIDE_A = 100.0        # A80 and A100 are never divided


def can_divide(a: float, n: int) -> bool:
    return a > MIN_DIVIDE_A + 1e-9 and n >= 3


def hole_counts(n: int):
    """[(name, quantity, holes per section)] for the unique sections."""
    q, r = divmod(n, 3)
    if r == 0:
        return [("Section", 3, q)]
    if r == 1:
        return [("Section A", 2, q), ("Section B", 1, q + 1)]
    return [("Section A", 2, q + 1), ("Section B", 1, q)]


@dataclass
class SectionPlan:
    name: str
    quantity: int
    holes: List[int]          # hole indices in this section
    a0: float                 # start cut angle [deg]
    a1: float                 # end cut angle [deg] (a1 > a0)

    @property
    def span(self):
        return self.a1 - self.a0

    @property
    def mid(self):
        return 0.5 * (self.a0 + self.a1)


def plan(n: int, start_angle: float = 90.0) -> List[SectionPlan]:
    """Unique sections of a flange with n holes, hole k at start + 360 k / n.
    Section B (or the single section) is centred as close to the bottom
    (270 deg) as the hole pattern allows; A follows counter-clockwise."""
    step = 360.0 / n
    counts = hole_counts(n)
    sizes = []                                         # all three sections, in order
    if len(counts) == 1:
        sizes = [counts[0]] * 3
    else:
        a, b = counts
        sizes = [b, a, a]                              # B first, then the two A
    hb = sizes[0][2]

    def centre(i, h):                                  # middle angle of h holes starting at i
        return start_angle + step * (i + (h - 1) / 2.0)

    def off_bottom(i):
        d = (centre(i, hb) - 270.0) % 360.0
        return min(d, 360.0 - d)

    first = min(range(n), key=off_bottom)
    out, i, seen = [], first, set()
    for name, qty, h in sizes:
        idx = [(i + k) % n for k in range(h)]
        a0 = start_angle + step * i - step / 2
        sec = SectionPlan(name, qty, idx, a0, a0 + h * step)
        if name not in seen:                           # only one drawing per kind
            out.append(sec)
            seen.add(name)
        i += h
    out.sort(key=lambda sec: sec.name)                 # Section A before Section B
    return out


def cut_angles(n: int, start_angle: float = 90.0) -> List[float]:
    """The three cut angles [deg] on the whole flange."""
    step = 360.0 / n
    secs = plan(n, start_angle)
    counts = hole_counts(n)
    if len(counts) == 1:
        a, sizes = secs[0].a0, [counts[0][2]] * 3
    else:
        a = [sec for sec in secs if sec.name == "Section B"][0].a0
        sizes = [counts[1][2], counts[0][2], counts[0][2]]           # B, A, A
    cuts = []
    for h in sizes:
        cuts.append(a % 360.0)
        a += h * step
    return cuts


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
