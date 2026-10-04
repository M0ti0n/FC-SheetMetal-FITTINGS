# SPDX-License-Identifier: LGPL-2.1-or-later
"""Approximate a smooth curve y = f(x) with circular arcs (and lines).

No splines anywhere: CAM / laser / plasma controllers cut arcs natively,
so every cut curve is turned into a chain of arcs whose maximum deviation
from the true development curve is below `tol` (default 0.01 mm).

Each arc goes through three points ON the true curve (both ends and the
middle), so consecutive arcs share their end points exactly.
"""

import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

Point = Tuple[float, float]

DEFAULT_TOL = 0.01      # mm
MIN_SPAN = 1e-3         # mm, never split below this


@dataclass
class Seg:
    """A line (mid=None) or an arc through start, mid, end."""
    start: Point
    end: Point
    mid: Optional[Point] = None

    @property
    def is_arc(self):
        return self.mid is not None

    def reversed(self):
        return Seg(self.end, self.start, self.mid)

    def mapped(self, fn):
        return Seg(fn(self.start), fn(self.end), fn(self.mid) if self.mid else None)

    def bulge(self):
        """DXF bulge for the segment start -> end (0 for a line)."""
        if not self.is_arc:
            return 0.0
        c = circle_through(self.start, self.mid, self.end)
        if c is None:
            return 0.0
        (cx, cy), _ = c
        a0 = math.atan2(self.start[1] - cy, self.start[0] - cx)
        am = math.atan2(self.mid[1] - cy, self.mid[0] - cx)
        a1 = math.atan2(self.end[1] - cy, self.end[0] - cx)
        ccw = (a1 - a0) % (2 * math.pi)
        if (am - a0) % (2 * math.pi) <= ccw:      # mid lies on the CCW path
            sweep = ccw
        else:
            sweep = -((a0 - a1) % (2 * math.pi))
        return math.tan(sweep / 4.0)

    def sample(self, n=16) -> List[Point]:
        """Points along the segment (for previews / tests)."""
        if not self.is_arc:
            return [self.start, self.end]
        (cx, cy), r = circle_through(self.start, self.mid, self.end)
        a0 = math.atan2(self.start[1] - cy, self.start[0] - cx)
        sweep = 4 * math.atan(self.bulge())
        return [(cx + r * math.cos(a0 + sweep * i / n), cy + r * math.sin(a0 + sweep * i / n))
                for i in range(n + 1)]


def circle_through(a: Point, b: Point, c: Point):
    """Centre and radius of the circle through 3 points, None if collinear."""
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay)
          + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx)
          + (cx * cx + cy * cy) * (bx - ax)) / d
    return (ux, uy), math.hypot(ax - ux, ay - uy)


def _line_dev(a: Point, b: Point, p: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    return abs(dx * (p[1] - a[1]) - dy * (p[0] - a[0])) / L


def fit(f: Callable[[float], float], x0: float, x1: float,
        tol: float = DEFAULT_TOL, checks: int = 8) -> List[Seg]:
    """Arcs/lines approximating y = f(x) from x0 to x1 within `tol`."""
    out: List[Seg] = []

    def rec(a, b, depth):
        pa, pb = (a, f(a)), (b, f(b))
        m = 0.5 * (a + b)
        pm = (m, f(m))
        probes = [(a + (b - a) * k / (checks + 1)) for k in range(1, checks + 1)]
        probes = [(x, f(x)) for x in probes]
        # straight enough -> line
        if max(_line_dev(pa, pb, p) for p in probes + [pm]) <= tol:
            out.append(Seg(pa, pb))
            return
        circ = circle_through(pa, pm, pb)
        chord = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        if circ is not None and circ[1] > 1000 * chord:
            circ = None          # numerically a line, but the line test failed
        if circ is not None:
            seg = Seg(pa, pb, pm)
            if _arc_dev(seg, f, checks * 2) <= tol:
                out.append(seg)
                return
        if b - a < MIN_SPAN or depth > 40:
            out.append(Seg(pa, pb, pm) if circ else Seg(pa, pb))
            return
        rec(a, m, depth + 1)
        rec(m, b, depth + 1)

    rec(x0, x1, 0)
    return out


def _arc_dev(seg: Seg, f, n: int) -> float:
    """Vertical gap between arc and curve (>= the true normal distance)."""
    return max(abs(y - f(x)) for x, y in seg.sample(n))


def max_deviation(segs: List[Seg], f: Callable[[float], float], n: int = 200) -> float:
    """Largest distance between the true curve and the fitted chain."""
    worst = 0.0
    for s in segs:
        if s.is_arc:
            worst = max(worst, _arc_dev(s, f, n))
        else:
            a, b = sorted((s.start[0], s.end[0]))
            for k in range(n + 1):
                x = a + (b - a) * k / n
                worst = max(worst, _line_dev(s.start, s.end, (x, f(x))))
    return worst


def fit_points(points: List[Point], tol: float = DEFAULT_TOL) -> List[Seg]:
    """Arcs/lines through a dense chain of points (a sampled smooth curve).

    Each arc runs through three of the given points (both ends + middle);
    it is accepted when every intermediate point is within `tol` of it.
    """
    out: List[Seg] = []
    pts = list(points)

    def dev_line(i, j):
        return max((_line_dev(pts[i], pts[j], pts[k]) for k in range(i + 1, j)), default=0.0)

    def rec(i, j):
        if j - i < 2 or dev_line(i, j) <= tol:
            out.append(Seg(pts[i], pts[j]))
            return
        m = (i + j) // 2
        circ = circle_through(pts[i], pts[m], pts[j])
        chord = math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1])
        if circ is not None and circ[1] < 1000 * chord:
            (cx, cy), r = circ
            if max(abs(math.hypot(pts[k][0] - cx, pts[k][1] - cy) - r) for k in range(i + 1, j)) <= tol:
                out.append(Seg(pts[i], pts[j], pts[m]))
                return
        if j - i == 2:
            out.append(Seg(pts[i], pts[m]))
            out.append(Seg(pts[m], pts[j]))
            return
        rec(i, m)
        rec(m, j)

    rec(0, len(pts) - 1)
    return out
