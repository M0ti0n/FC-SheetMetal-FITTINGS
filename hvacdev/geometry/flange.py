# SPDX-License-Identifier: LGPL-2.1-or-later
"""Flat ring flange with arc slots - flat pattern (pure Python).

    A  inner (nominal) diameter
    E  ring width -> outer diameter D = A + 2 E (information)
    B  diameter of the circle the slots lie on
    M  slot width
    N  number of slots, equally spaced, the first one at the top
    T  recommended thickness (information only)

Each slot is an arc slot along the B circle; its two end-hole centres are
SLOT_LENGTH (25 mm) apart (straight distance). The pattern is centred at
(D/2, D/2) so it starts at x = 0, y = 0 like the other tools.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from . import arcs
from .flange_table import SIZES

Point = Tuple[float, float]
SLOT_LENGTH = 25.0          # distance between the end-hole centres of a slot [mm]
MIN_WEB = 1.0               # minimum material left between slot and ring edge / next slot [mm]


@dataclass
class FlangeParams:
    a: float = 400.0          # inner diameter
    b: float = 435.0          # slot circle diameter
    m: float = 11.0           # slot width
    n: int = 10               # number of slots
    e: float = 30.0           # ring width
    t: float = 8.0            # thickness (information)
    start_angle: float = 90.0  # first slot position [deg], 90 = top

    @property
    def d(self):
        return self.a + 2 * self.e

    def slot_half_angle(self):
        """Half the angle between the two end-hole centres of a slot [rad]."""
        return math.asin(min(1.0, (SLOT_LENGTH / 2) / (self.b / 2)))

    def validate(self) -> List[str]:
        err = []
        if self.a <= 0:
            err.append("A must be greater than 0.")
        if self.e <= 0:
            err.append("E must be greater than 0.")
        if self.m <= 0:
            err.append("M must be greater than 0.")
        if self.n < 1:
            err.append("N must be at least 1.")
        if self.b <= SLOT_LENGTH:
            err.append("B is too small for a %g mm slot." % SLOT_LENGTH)
        if err:
            return err
        rb, w = self.b / 2, self.m / 2
        if rb - w < self.a / 2 + MIN_WEB:
            err.append("The slots cut into the inner edge: B - M must be larger than A "
                       "(B %.1f, M %.1f, A %.1f)." % (self.b, self.m, self.a))
        if rb + w > self.a / 2 + self.e - MIN_WEB:
            err.append("The slots cut into the outer edge: B + M must be smaller than D = A + 2E "
                       "(B %.1f, M %.1f, D %.1f)." % (self.b, self.m, self.d))
        # neighbouring slots must not touch: angular room per slot
        half = self.slot_half_angle() + math.asin(min(1.0, w / (rb - w)))
        if self.n > 1 and 2 * half + MIN_WEB / rb >= 2 * math.pi / self.n:
            err.append("%d slots do not fit on the B circle - use fewer slots." % self.n)
        return err


def table_row(a: float) -> Optional[tuple]:
    for row in SIZES:
        if abs(row[0] - a) < 1e-9:
            return row
    return None


def params_for(a: float) -> Tuple[FlangeParams, bool]:
    """Parameters for size A from the table. For a size that is not in the
    table the nearest smaller size is used as template (same M, N, E, T and the
    same B - A offset). Returns (params, from_table)."""
    row = table_row(a)
    if row:
        A, B, M, N, E, T = row
        return FlangeParams(a=A, b=B, m=M, n=N, e=E, t=T), True
    smaller = [r for r in SIZES if r[0] < a]
    A0, B0, M, N, E, T = smaller[-1] if smaller else SIZES[0]
    return FlangeParams(a=a, b=a + (B0 - A0), m=M, n=N, e=E, t=T), False


@dataclass
class FlangePattern:
    outer: List[arcs.Seg]
    inner: List[arcs.Seg]
    slots: List[List[arcs.Seg]]
    centre: Point
    hole_centres: List[Point] = field(default_factory=list)   # 3 per slot: end, middle, end
    slot_angles: List[float] = field(default_factory=list)    # [deg]

    @property
    def contours(self):
        return [self.outer, self.inner] + self.slots

    def bbox(self):
        cx, cy = self.centre
        r = math.dist(self.outer[0].start, self.centre)
        return cx - r, cy - r, cx + r, cy + r


def _circle(c, r):
    """Full circle as two arcs (no splines, no zero-length chord)."""
    cx, cy = c
    p0, p1 = (cx + r, cy), (cx - r, cy)
    return [arcs.Seg(p0, p1, (cx, cy + r)), arcs.Seg(p1, p0, (cx, cy - r))]


def _slot(c, p: FlangeParams, phi):
    """Closed arc slot centred at angle phi (rad): outer arc, end cap, inner arc, end cap."""
    cx, cy = c
    rb, w = p.b / 2, p.m / 2
    h = p.slot_half_angle()

    def P(r, a):
        return (cx + r * math.cos(a), cy + r * math.sin(a))

    def cap(a_end, outward):
        """Half circle of radius w around the end-hole centre at angle a_end,
        from the outer to the inner slot edge, bulging in direction `outward`."""
        ec = P(rb, a_end)
        radial = (math.cos(a_end), math.sin(a_end))
        tang = (-math.sin(a_end) * outward, math.cos(a_end) * outward)
        start = (ec[0] + radial[0] * w, ec[1] + radial[1] * w)
        mid = (ec[0] + tang[0] * w, ec[1] + tang[1] * w)
        end = (ec[0] - radial[0] * w, ec[1] - radial[1] * w)
        return arcs.Seg(start, end, mid)

    a0, a1 = phi - h, phi + h
    return [
        arcs.Seg(P(rb + w, a0), P(rb + w, a1), P(rb + w, phi)),        # outer edge
        cap(a1, +1),                                                    # end cap at a1
        arcs.Seg(P(rb - w, a1), P(rb - w, a0), P(rb - w, phi)),        # inner edge
        cap(a0, -1).reversed(),                                         # end cap at a0
    ]


def develop(p: FlangeParams) -> FlangePattern:
    errors = p.validate()
    if errors:
        raise ValueError("\n".join(errors))
    c = (p.d / 2, p.d / 2)
    pat = FlangePattern(outer=_circle(c, p.d / 2), inner=_circle(c, p.a / 2), slots=[], centre=c)
    h = p.slot_half_angle()
    for k in range(p.n):
        phi_deg = p.start_angle + 360.0 * k / p.n
        phi = math.radians(phi_deg)
        pat.slots.append(_slot(c, p, phi))
        pat.slot_angles.append(phi_deg % 360.0)
        for a in (phi - h, phi, phi + h):
            pat.hole_centres.append((c[0] + p.b / 2 * math.cos(a), c[1] + p.b / 2 * math.sin(a)))
    return pat
