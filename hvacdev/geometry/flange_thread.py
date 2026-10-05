# SPDX-License-Identifier: LGPL-2.1-or-later
"""Flat ring flange with threaded holes, marked by crosses (pure Python).

    A  inner (nominal) diameter
    E  ring width -> outer diameter D = A + 2 E (information)
    B  diameter of the circle the holes lie on
    M  metric thread (M6, M8, ...) - holes are drilled and tapped after cutting
    N  number of holes, equally spaced, the first one at the top
    T  recommended thickness (information only)

The cut contour is only the outer and inner circle. Each hole position gets
an X-shaped cross mark (two lines at 45 deg to the radius) for scribing /
punching; the marks go to their own layer (MARK).
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from . import arcs
from .flange import _circle, MIN_WEB
from .flange_thread_table import SIZES, THREADS

Point = Tuple[float, float]


def thread_diameter(m: str) -> float:
    """Nominal diameter of a metric thread, e.g. 'M8' -> 8.0."""
    m = m.strip().upper()
    if m in THREADS:
        return THREADS[m][0]
    try:
        return float(m.lstrip("M").replace(",", "."))
    except ValueError:
        raise ValueError("Unknown thread '%s' - use M6, M8, M10, ..." % m)


def tap_drill(m: str) -> float:
    """Tap drill for an ISO coarse thread (approximation for sizes not in the list)."""
    m = m.strip().upper()
    if m in THREADS:
        return THREADS[m][1]
    return round(thread_diameter(m) * 0.84, 1)


@dataclass
class ThreadFlangeParams:
    a: float = 400.0
    b: float = 435.0
    m: str = "M8"
    n: int = 10
    e: float = 30.0
    t: float = 10.0
    mark_size: float = 10.0        # overall size of a cross mark [mm]
    start_angle: float = 90.0

    @property
    def d(self):
        return self.a + 2 * self.e

    def validate(self) -> List[str]:
        err = []
        if self.a <= 0:
            err.append("A must be greater than 0.")
        if self.e <= 0:
            err.append("E must be greater than 0.")
        if self.n < 1:
            err.append("N must be at least 1.")
        if self.mark_size <= 0:
            err.append("The cross mark size must be greater than 0.")
        try:
            dt = thread_diameter(self.m)
        except ValueError as exc:
            return err + [str(exc)]
        if err:
            return err
        rb, r = self.b / 2, dt / 2
        if rb - r < self.a / 2 + MIN_WEB:
            err.append("The %s holes cut into the inner edge: B - %g must be larger than A "
                       "(B %.1f, A %.1f)." % (self.m, dt, self.b, self.a))
        if rb + r > self.a / 2 + self.e - MIN_WEB:
            err.append("The %s holes cut into the outer edge: B + %g must be smaller than D = A + 2E "
                       "(B %.1f, D %.1f)." % (self.m, dt, self.b, self.d))
        if self.n > 1 and 2 * rb * math.sin(math.pi / self.n) < dt + MIN_WEB:
            err.append("%d %s holes do not fit on the B circle - use fewer holes." % (self.n, self.m))
        return err


def table_row(a: float) -> Optional[tuple]:
    for row in SIZES:
        if abs(row[0] - a) < 1e-9:
            return row
    return None


def params_for(a: float) -> Tuple[ThreadFlangeParams, bool]:
    """Table values for size A; any other A takes the nearest smaller size as
    template (same M, N, E, T and B - A offset). Returns (params, from_table)."""
    row = table_row(a)
    if row:
        A, B, M, N, E, T = row
        return ThreadFlangeParams(a=A, b=B, m=M, n=N, e=E, t=T), True
    smaller = [r for r in SIZES if r[0] < a]
    A0, B0, M, N, E, T = smaller[-1] if smaller else SIZES[0]
    return ThreadFlangeParams(a=a, b=a + (B0 - A0), m=M, n=N, e=E, t=T), False


@dataclass
class ThreadFlangePattern:
    outer: List[arcs.Seg]
    inner: List[arcs.Seg]
    centre: Point
    hole_centres: List[Point] = field(default_factory=list)
    hole_angles: List[float] = field(default_factory=list)            # [deg]
    marks: List[Tuple[Point, Point]] = field(default_factory=list)    # 2 lines per hole

    @property
    def contours(self):
        return [self.outer, self.inner]

    def bbox(self):
        cx, cy = self.centre
        r = math.dist(self.outer[0].start, self.centre)
        return cx - r, cy - r, cx + r, cy + r


def develop(p: ThreadFlangeParams) -> ThreadFlangePattern:
    errors = p.validate()
    if errors:
        raise ValueError("\n".join(errors))
    c = (p.d / 2, p.d / 2)
    pat = ThreadFlangePattern(outer=_circle(c, p.d / 2), inner=_circle(c, p.a / 2), centre=c)
    arm = p.mark_size / 2
    for k in range(p.n):
        phi_deg = p.start_angle + 360.0 * k / p.n
        phi = math.radians(phi_deg)
        h = (c[0] + p.b / 2 * math.cos(phi), c[1] + p.b / 2 * math.sin(phi))
        pat.hole_centres.append(h)
        pat.hole_angles.append(phi_deg % 360.0)
        for d in (math.pi / 4, -math.pi / 4):                    # X: 45 deg to the radius
            ux, uy = math.cos(phi + d), math.sin(phi + d)
            pat.marks.append(((h[0] - ux * arm, h[1] - uy * arm), (h[0] + ux * arm, h[1] + uy * arm)))
    return pat
