# SPDX-License-Identifier: LGPL-2.1-or-later
"""Segmented (gored) round elbow - flat pattern development.

Pure Python, no FreeCAD dependency, so it can be unit tested anywhere.

Conventions (HACO style)
------------------------
* All geometry is on the neutral surface: D is the neutral diameter,
  no sheet thickness and no K-factor.
* N = number of FULL middle sections. Two end sections are always added
  and each end section is exactly half of a middle section, cut
  perpendicular to the duct axis.
* The elbow angle A is therefore split into (N + 1) equal steps:
      theta = A / (N + 1)
  A middle section spans theta, each end section spans theta / 2.

Development of one middle section
---------------------------------
Unroll the cylinder; x runs along the circumference (0 .. pi*D) and y
along the duct axis, with y = 0 on the mid-plane of the section.
For the generator at angle phi (phi = 0 on the heel / outer side,
phi = pi on the throat / inner side) the cut height is

      h(phi) = (R + r*cos(phi)) * tan(theta / 2),     r = D / 2

Middle section: top edge y = +h(phi), bottom edge y = -h(phi).
End section:    square edge y = 0,    mitre edge y = +h(phi).
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple

from . import arcs

Point = Tuple[float, float]

SEAM_THROAT = "Throat"   # seam on the inner (shortest) generator
SEAM_HEEL = "Heel"       # seam on the outer (longest) generator
SEAM_SIDE = "Side"       # seam on the side generator (mid-length seam) - default
SEAM_POSITIONS = (SEAM_SIDE, SEAM_THROAT, SEAM_HEEL)


@dataclass
class ElbowParams:
    diameter: float = 400.0          # D, neutral diameter [mm]
    angle: float = 90.0              # A, elbow angle [deg]
    radius: float = 800.0            # R, centreline radius [mm]
    middle_sections: int = 3         # N, full middle sections
    fold_lines: int = 24             # number of press-brake fold lines
    seam: str = SEAM_SIDE
    curve_points: int = 181          # sampling of the cut curves (tests/preview)
    arc_tol: float = 0.01            # max deviation of cut arcs from the true curve [mm]
    fold_mark_length: float = 15.0   # length of each fold mark [mm]
    fold_mark_gap: float = 2.0       # distance of the fold mark from the cut edge [mm]

    def validate(self) -> List[str]:
        err = []
        if self.diameter <= 0:
            err.append("Diameter (D) must be greater than 0.")
        if not 0 < self.angle < 180:
            err.append("Elbow angle (A) must be between 0 and 180 deg.")
        if self.middle_sections < 0:
            err.append("Number of middle sections (N) cannot be negative.")
        if self.radius < self.diameter / 2:
            err.append("Centreline radius (R) must be at least D/2, "
                       "otherwise the throat folds over itself.")
        if self.fold_mark_length <= 0 or self.fold_mark_gap < 0:
            err.append("Fold mark length must be > 0 and the edge gap >= 0.")
        if self.fold_lines < 0:
            err.append("Number of folding lines cannot be negative.")
        if self.seam not in SEAM_POSITIONS:
            err.append("Unknown seam position '%s'." % self.seam)
        return err


@dataclass
class Section:
    """One developed piece, in its own local coordinates (x from 0)."""
    name: str
    quantity: int
    outline: List[Point]                              # closed, sampled (tests / preview)
    contour: List["arcs.Seg"] = field(default_factory=list)   # closed: lines + arcs only
    fold_lines: List[Tuple[Point, Point]] = field(default_factory=list)   # full fold position, edge to edge
    fold_marks: List[Tuple[Point, Point]] = field(default_factory=list)   # what is drawn / cut: short marks
    fold_angle: float = 0.0                           # bend angle per fold [deg]
    reference_lines: List[Tuple[Point, Point]] = field(default_factory=list)
    reference_labels: List[Tuple[Point, str]] = field(default_factory=list)
    width: float = 0.0                                # developed length = pi*D
    h_max: float = 0.0
    h_min: float = 0.0

    def bbox(self):
        xs = [p[0] for p in self.outline]
        ys = [p[1] for p in self.outline]
        return min(xs), min(ys), max(xs), max(ys)


def segment_angle(p: ElbowParams) -> float:
    """Angle (deg) spanned by one middle section."""
    return p.angle / (p.middle_sections + 1)


def _phi_at_x(x: float, p: ElbowParams) -> float:
    """Generator angle phi (0 = heel) for a position x along the pattern."""
    r = p.diameter / 2.0
    start = {SEAM_THROAT: math.pi, SEAM_HEEL: 0.0, SEAM_SIDE: math.pi / 2}[p.seam]
    return start + x / r


def cut_height(x: float, p: ElbowParams) -> float:
    r = p.diameter / 2.0
    t = math.tan(math.radians(segment_angle(p)) / 2.0)
    return (p.radius + r * math.cos(_phi_at_x(x, p))) * t


def _curve(p: ElbowParams, sign: float = 1.0) -> List[Point]:
    width = math.pi * p.diameter
    n = max(8, p.curve_points)
    return [(width * i / (n - 1), sign * cut_height(width * i / (n - 1), p))
            for i in range(n)]


def _fold_xs(p: ElbowParams) -> List[float]:
    """Fold lines evenly spaced around the circumference.

    They sit in the middle of the facets measured from the seam, so the
    seam never lands on a fold.
    """
    if p.fold_lines <= 0:
        return []
    width = math.pi * p.diameter
    step = width / p.fold_lines
    return [step * (i + 0.5) for i in range(p.fold_lines)]


def fold_marks(x: float, y_low: float, y_high: float, p: ElbowParams):
    """Two short marks on one fold: `fold_mark_length` long, starting
    `fold_mark_gap` inside each cut edge. If the piece is too short for two
    separate marks, they merge into one line (still keeping the edge gaps)."""
    g, L = p.fold_mark_gap, p.fold_mark_length
    a0, a1 = y_low + g, y_low + g + L
    b0, b1 = y_high - g - L, y_high - g
    if a1 >= b0:                        # marks would touch or overlap
        if y_high - y_low <= 2 * g + 0.5:   # too short for a useful mark (< 0.5 mm)
            return []
        return [((x, y_low + g), (x, y_high - g))]
    return [((x, a0), (x, a1)), ((x, b0), (x, b1))]


def _quarter_xs(p: ElbowParams) -> List[Tuple[float, str]]:
    """Heel / side / throat reference generators, labelled."""
    width = math.pi * p.diameter
    r = p.diameter / 2.0
    marks = []
    for phi, label in ((0.0, "HEEL"), (math.pi / 2, "SIDE"),
                       (math.pi, "THROAT"), (3 * math.pi / 2, "SIDE")):
        start = _phi_at_x(0.0, p)
        x = ((phi - start) % (2 * math.pi)) * r
        if 1e-6 < x < width - 1e-6:
            marks.append((x, label))
    return sorted(marks)


def develop(p: ElbowParams) -> Tuple[Section, Section]:
    """Return (middle_section, end_section) flat patterns."""
    errors = p.validate()
    if errors:
        raise ValueError("\n".join(errors))

    width = math.pi * p.diameter
    top = _curve(p, +1.0)
    bottom = _curve(p, -1.0)
    heights = [y for _, y in top]
    fold_angle = 360.0 / p.fold_lines if p.fold_lines else 0.0

    # ---- middle section: symmetric about y = 0
    mid_outline = top + list(reversed(bottom)) + [top[0]]
    middle = Section("Middle Section", p.middle_sections, mid_outline,
                     width=width, h_max=max(heights), h_min=min(heights),
                     fold_angle=fold_angle)
    for x in _fold_xs(p):
        h = cut_height(x, p)
        middle.fold_lines.append(((x, -h), (x, h)))
        middle.fold_marks += fold_marks(x, -h, h, p)
    top_arcs = arcs.fit(lambda x: cut_height(x, p), 0.0, width, p.arc_tol)
    bottom_arcs = [sg.mapped(lambda q: (q[0], -q[1])) for sg in top_arcs]
    t0, t1 = top_arcs[0].start, top_arcs[-1].end
    middle.contour = (top_arcs
                      + [arcs.Seg(t1, (t1[0], -t1[1]))]
                      + [sg.reversed() for sg in reversed(bottom_arcs)]
                      + [arcs.Seg((t0[0], -t0[1]), t0)])
    middle.reference_lines.append(((0.0, 0.0), (width, 0.0)))   # mid-plane
    for x, label in _quarter_xs(p):
        h = cut_height(x, p)
        middle.reference_lines.append(((x, -h), (x, h)))
        middle.reference_labels.append(((x, 0.0), label))

    # ---- end section: half of the middle section, square edge at y = 0
    end_outline = [(0.0, 0.0), (width, 0.0)] + list(reversed(top)) + [(0.0, 0.0)]
    end = Section("End Section", 2, end_outline,
                  width=width, h_max=max(heights), h_min=min(heights),
                  fold_angle=fold_angle)
    end.contour = ([arcs.Seg((0.0, 0.0), (width, 0.0)), arcs.Seg((width, 0.0), t1)]
                   + [sg.reversed() for sg in reversed(top_arcs)]
                   + [arcs.Seg(t0, (0.0, 0.0))])
    for x in _fold_xs(p):
        end.fold_lines.append(((x, 0.0), (x, cut_height(x, p))))
        end.fold_marks += fold_marks(x, 0.0, cut_height(x, p), p)
    for x, label in _quarter_xs(p):
        end.reference_lines.append(((x, 0.0), (x, cut_height(x, p))))
        end.reference_labels.append(((x, 0.0), label))

    return middle, end


def summary(p: ElbowParams) -> dict:
    middle, end = develop(p)
    return {
        "segment_angle": segment_angle(p),
        "developed_length": middle.width,
        "middle_heel": 2 * (p.radius + p.diameter / 2) * math.tan(math.radians(segment_angle(p)) / 2),
        "middle_throat": 2 * (p.radius - p.diameter / 2) * math.tan(math.radians(segment_angle(p)) / 2),
        "end_heel": (p.radius + p.diameter / 2) * math.tan(math.radians(segment_angle(p)) / 2),
        "end_throat": (p.radius - p.diameter / 2) * math.tan(math.radians(segment_angle(p)) / 2),
    }
