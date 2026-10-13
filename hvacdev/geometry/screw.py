# SPDX-License-Identifier: LGPL-2.1-or-later
"""Screw conveyor / Archimedes screw flight - blank for one pitch (pure Python).

    OD  outer diameter of the flight
    ID  inner diameter of the flight (= shaft diameter)
    P   pitch (one full turn along the axis)
    L   screw length -> number of pieces = ceil(L / P)
    GAP gap left between the two cut ends at the inner edge (default 6 mm)

Blank (annular ring with a gap), standard development:
    Li = sqrt((pi ID)^2 + P^2)       inner helix length of one turn
    Lo = sqrt((pi OD)^2 + P^2)       outer helix length of one turn
    h  = (OD - ID) / 2               flight width
    Ri = h Li / (Lo - Li)            inner radius of the blank
    Ro = Ri + h                      outer radius of the blank
    angle = Li / Ri                  calculated blank angle (< 360 deg)

The inner and outer edges then have exactly the helix lengths. A flight
cannot be developed exactly (a helicoid is not developable): between the
edges the blank is 1-4 % longer than the helix and is stretched when formed.

Shop practice: the calculated blank is extended until the two cut ends are
GAP mm apart (straight distance) at the inner edge, the closest point:
    gap angle   = 2 asin(GAP / 2 / Ri)
    blank angle = 360 - gap angle
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple

from . import arcs

Point = Tuple[float, float]


@dataclass
class ScrewParams:
    od: float = 315.0
    id: float = 101.6
    pitch: float = 300.0
    length: float = 1000.0
    gap: float = 6.0

    def validate(self) -> List[str]:
        err = []
        if self.id <= 0:
            err.append("ID must be greater than 0.")
        if self.od <= self.id:
            err.append("OD must be larger than ID.")
        if self.pitch <= 0:
            err.append("P must be greater than 0.")
        if self.length <= 0:
            err.append("L must be greater than 0.")
        if self.gap < 0:
            err.append("The gap cannot be negative.")
        return err


@dataclass
class ScrewResult:
    inner_helix: float          # Li
    outer_helix: float          # Lo
    width: float                # h
    ri: float
    ro: float
    calc_angle: float           # [deg] calculated blank angle (black part)
    gap_angle: float            # [deg]
    blank_angle: float          # [deg] blank angle to cut (black + green)
    extension: float            # [deg] green part
    gap_outer: float            # straight distance between the cut ends at the outer edge
    pieces: int
    turns: float                # L / P
    warnings: List[str] = field(default_factory=list)


def calculate(p: ScrewParams) -> ScrewResult:
    errors = p.validate()
    if errors:
        raise ValueError("\n".join(errors))
    li = math.hypot(math.pi * p.id, p.pitch)
    lo = math.hypot(math.pi * p.od, p.pitch)
    h = (p.od - p.id) / 2.0
    ri = h * li / (lo - li)
    ro = ri + h
    calc = math.degrees(li / ri)
    warnings = []
    if p.gap >= 2 * ri:
        raise ValueError("The gap (%g mm) is larger than the inner blank diameter (%.1f mm)." % (p.gap, 2 * ri))
    gap_angle = math.degrees(2 * math.asin(p.gap / 2.0 / ri))
    blank = 360.0 - gap_angle
    if blank < calc:
        # the calculated blank already needs more than the ring allows with this gap
        warnings.append("The calculated blank (%.2f deg) is larger than 360 deg minus the %g mm gap - "
                        "the blank is not extended and the gap is smaller." % (calc, p.gap))
        blank = calc
        gap_angle = 360.0 - calc
    turns = p.length / p.pitch
    pieces = max(1, math.ceil(turns - 1e-9))
    gap_outer = 2 * ro * math.sin(math.radians(gap_angle) / 2)
    return ScrewResult(li, lo, h, ri, ro, calc, gap_angle, blank, blank - calc, gap_outer, pieces, turns,
                       warnings)


@dataclass
class ScrewBlank:
    contour: List[arcs.Seg]
    centre: Point
    result: ScrewResult
    calc_end: Tuple[Point, Point]       # radial line where the calculated (black) part ends
    a_start: float                      # [deg] blank start angle (one cut edge)
    a_end: float                        # [deg] blank end angle (other cut edge)

    def bbox(self):
        r = self.result.ro
        return self.centre[0] - r, self.centre[1] - r, self.centre[0] + r, self.centre[1] + r


def develop(p: ScrewParams) -> ScrewBlank:
    """The blank, centred at (Ro, Ro), gap at the bottom (270 deg).
    The blank runs counter-clockwise from the right cut edge to the left one;
    the calculated part starts at the right cut edge."""
    r = calculate(p)
    c = (r.ro, r.ro)
    a0 = 270.0 + r.gap_angle / 2.0              # right cut edge
    a1 = a0 + r.blank_angle                     # left cut edge (= 270 - gap/2 + 360)

    def P(rad, deg):
        a = math.radians(deg)
        return (c[0] + rad * math.cos(a), c[1] + rad * math.sin(a))

    k = max(1, math.ceil(r.blank_angle / 90.0))
    span = r.blank_angle
    outer = [arcs.Seg(P(r.ro, a0 + span * i / k), P(r.ro, a0 + span * (i + 1) / k),
                      P(r.ro, a0 + span * (i + 0.5) / k)) for i in range(k)]
    inner = [arcs.Seg(P(r.ri, a1 - span * i / k), P(r.ri, a1 - span * (i + 1) / k),
                      P(r.ri, a1 - span * (i + 0.5) / k)) for i in range(k)]
    contour = outer + [arcs.Seg(P(r.ro, a1), P(r.ri, a1))] + inner + [arcs.Seg(P(r.ri, a0), P(r.ro, a0))]
    ce = a0 + r.calc_angle
    return ScrewBlank(contour, c, r, (P(r.ri, ce), P(r.ro, ce)), a0, a1)
