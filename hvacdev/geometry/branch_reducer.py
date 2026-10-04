# SPDX-License-Identifier: LGPL-2.1-or-later
"""Reducer (cone frustum) with a round branch - flat patterns.

Pure Python, no FreeCAD dependency. Neutral surface, no thickness.

Geometry (side view = the task-panel diagram)
--------------------------------------------
Reducer: round cone frustum on the z axis, diameter D2 at z = 0, D1 at z = H1.
Branch:  round pipe D3 on the left (-x) side. Its axis lies in the x-z plane,
         rises at angle A above the horizontal and meets the reducer side at
         height H2 (point P). The branch end is square to the axis, at
         distance L from P along the axis.

Seams
-----
Reducer: on the generator that passes through the middle of the branch hole
         (the -x generator), so the hole is split into two halves, one on
         each seam edge of the pattern.
Branch:  on its shortest generator (the top one in the diagram).

The hole and the branch end curve come from the exact intersection of the
branch cylinder with the cone; all curves are written as arcs (no splines).
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple

from . import arcs
from .marks import fold_marks_on_line

Point = Tuple[float, float]

HOLE_SAMPLES = 360          # intersection points around the branch


@dataclass
class BranchReducerParams:
    d1: float = 200.0         # top diameter of the reducer
    d2: float = 400.0         # bottom diameter of the reducer
    h1: float = 400.0         # reducer height
    h2: float = 200.0         # height where the branch axis meets the reducer side
    d3: float = 160.0         # branch diameter
    length: float = 250.0     # L, from that point along the branch axis to the branch end
    angle: float = 30.0       # A, branch axis above the horizontal [deg]
    fold_lines: int = 24      # fold lines around each round part (0 = none)
    fold_mark_length: float = 15.0
    fold_mark_gap: float = 2.0
    arc_tol: float = 0.01

    def validate(self) -> List[str]:
        err = []
        for name, label in (("d1", "D1"), ("d2", "D2"), ("h1", "H1"), ("d3", "D3"), ("length", "L")):
            if getattr(self, name) <= 0:
                err.append("%s must be greater than 0." % label)
        if not 0 < self.h2 < self.h1:
            err.append("H2 must lie between 0 and H1.")
        if not -89.0 < self.angle < 90.0:
            err.append("A must be between -89 and 90 degrees.")
        if self.fold_lines < 0:
            err.append("Number of folding lines cannot be negative.")
        if self.fold_mark_length <= 0 or self.fold_mark_gap < 0:
            err.append("Fold mark length must be > 0 and the edge gap >= 0.")
        return err


@dataclass
class Piece:
    name: str
    quantity: int
    contour: List[arcs.Seg]
    outline: List[Point]
    fold_lines: List[Tuple[Point, Point]] = field(default_factory=list)
    fold_marks: List[Tuple[Point, Point]] = field(default_factory=list)
    ref_lines: List[Tuple[Point, Point]] = field(default_factory=list)
    ref_labels: List[Tuple[Point, str]] = field(default_factory=list)
    dims: List[Tuple[Point, Point, str]] = field(default_factory=list)   # edge to label + name
    seam_length: float = 0.0
    offset: Point = (0.0, 0.0)

    def bbox(self):
        xs = [p[0] for p in self.outline]
        ys = [p[1] for p in self.outline]
        return min(xs), min(ys), max(xs), max(ys)


# ------------------------------------------------------------------ 3D model
class _Model:
    def __init__(self, p: BranchReducerParams):
        self.p = p
        self.R2, self.R1 = p.d2 / 2.0, p.d1 / 2.0
        self.k = (self.R1 - self.R2) / p.h1          # radius change per height
        self.r3 = p.d3 / 2.0
        a = math.radians(p.angle)
        self.u = (-math.cos(a), 0.0, math.sin(a))    # branch axis, outwards
        self.n = (math.sin(a), 0.0, math.cos(a))     # "up" normal of the branch
        self.w = (0.0, 1.0, 0.0)
        self.P = (-self.R(p.h2), 0.0, p.h2)

    def R(self, z):
        return self.R2 + self.k * z

    def branch_point(self, beta, t):
        """Point on the branch surface: angle beta around the axis (0 = top), t along it."""
        P, u, n, w, r = self.P, self.u, self.n, self.w, self.r3
        c, s = math.cos(beta), math.sin(beta)
        return tuple(P[i] + t * u[i] + r * (c * n[i] + s * w[i]) for i in range(3))

    def _f(self, beta, t):
        x, y, z = self.branch_point(beta, t)
        return math.hypot(x, y) - self.R(z)

    def meet(self, beta):
        """t where the branch generator at beta meets the reducer (outer crossing)."""
        p = self.p
        step = (self.R2 + self.r3) / 400.0
        t_hi = p.length
        if self._f(beta, t_hi) <= 0:
            raise ValueError("The branch end lies inside the reducer - increase L.")
        t = t_hi
        t_min = -2.0 * (max(self.R1, self.R2) + self.r3 + p.length)
        while t > t_min:
            t_lo = t - step
            if self._f(beta, t_lo) < 0:
                a, b = t_lo, t
                for _ in range(80):
                    m = 0.5 * (a + b)
                    if self._f(beta, m) < 0:
                        a = m
                    else:
                        b = m
                return 0.5 * (a + b)
            t = t_lo
        raise ValueError("The branch does not meet the reducer.")


# ------------------------------------------------- reducer (cone) development
class _ConeDev:
    """Development of the frustum; phi_s = angle around the axis measured from
    the seam generator (the -x one), z = height."""

    def __init__(self, m: _Model):
        self.m = m
        k = m.k
        self.q = math.sqrt(1.0 + k * k)
        self.cyl = abs(k) < 1e-12
        if not self.cyl:
            self.z_apex = -m.R2 / k
            self.theta = 2.0 * math.pi * abs(k) / self.q        # developed sector angle

    def rho(self, z):
        return self.q * abs(z - self.z_apex)

    def xy(self, phi_s, z):
        m = self.m
        if self.cyl:
            return (m.R2 * phi_s, z)
        ang = math.pi / 2 + self.theta / 2 - phi_s * abs(m.k) / self.q
        r = self.rho(z)
        return (r * math.cos(ang), r * math.sin(ang))

    def arc(self, z, phi0, phi1):
        """Arc (or line for a cylinder) along height z from phi0 to phi1."""
        if self.cyl:
            return [arcs.Seg(self.xy(phi0, z), self.xy(phi1, z))]
        n = max(1, math.ceil(abs(phi1 - phi0) * abs(self.m.k) / self.q / (math.pi / 2)))
        segs = []
        for i in range(n):
            a = phi0 + (phi1 - phi0) * i / n
            b = phi0 + (phi1 - phi0) * (i + 1) / n
            segs.append(arcs.Seg(self.xy(a, z), self.xy(b, z), self.xy(0.5 * (a + b), z)))
        return segs


def _phi_s(x, y):
    return (math.atan2(y, x) - math.pi) % (2 * math.pi)


def develop(p: BranchReducerParams):
    """Returns (reducer_piece, branch_piece)."""
    errors = p.validate()
    if errors:
        raise ValueError("\n".join(errors))
    m = _Model(p)
    tol = p.arc_tol

    # ---- intersection curve, sampled around the branch
    betas = [2 * math.pi * i / HOLE_SAMPLES for i in range(HOLE_SAMPLES + 1)]
    ts = [m.meet(b) for b in betas]
    pts3 = [m.branch_point(b, t) for b, t in zip(betas, ts)]
    zs = [q[2] for q in pts3]
    margin = 1.0
    if min(zs) < margin or max(zs) > p.h1 - margin:
        raise ValueError("The branch hole runs past the top or bottom of the reducer "
                         "(hole from z = %.1f to %.1f) - change H2, D3 or A." % (min(zs), max(zs)))
    if any(m.R(z) <= 0 for z in zs):
        raise ValueError("Invalid reducer geometry.")

    reducer = _develop_reducer(p, m, betas, pts3, tol)
    branch = _develop_branch(p, m, betas, ts, tol)
    return reducer, branch


def _develop_reducer(p, m, betas, pts3, tol):
    cone = _ConeDev(m)
    half = HOLE_SAMPLES // 2
    z_top_hole = pts3[0][2]          # beta = 0: upper crossing, on the seam
    z_bot_hole = pts3[half][2]       # beta = pi: lower crossing, on the seam
    two_pi = 2 * math.pi

    # hole half with y > 0 (beta 0..pi) sits on the right seam edge (phi_s near 2 pi)
    right = []
    for i in range(half, -1, -1):                     # beta pi -> 0, from the lower crossing up
        x, y, z = pts3[i]
        ph = two_pi if i in (0, half) else _phi_s(x, y)
        right.append(cone.xy(ph, z))
    # hole half with y < 0 (beta pi..2 pi) sits on the left seam edge (phi_s near 0)
    left = []
    for i in range(HOLE_SAMPLES, half - 1, -1):       # beta 2 pi -> pi, from the upper crossing down
        x, y, z = pts3[i]
        ph = 0.0 if i in (HOLE_SAMPLES, half) else _phi_s(x, y)
        left.append(cone.xy(ph, z))

    c = []
    c += cone.arc(0.0, 0.0, two_pi)                                  # bottom edge
    c.append(arcs.Seg(cone.xy(two_pi, 0.0), right[0]))               # right seam, below the hole
    hole_right = arcs.fit_points(right, tol)
    c += hole_right                                                  # right half of the hole
    c.append(arcs.Seg(right[-1], cone.xy(two_pi, p.h1)))             # right seam, above the hole
    c += cone.arc(p.h1, two_pi, 0.0)                                 # top edge
    c.append(arcs.Seg(cone.xy(0.0, p.h1), left[0]))                  # left seam, above the hole
    hole_left = arcs.fit_points(left, tol)
    c += hole_left                                                   # left half of the hole
    c.append(arcs.Seg(left[-1], cone.xy(0.0, 0.0)))                  # left seam, below the hole

    outline = _sampled_outline(c)
    slant = cone.q * p.h1
    pc = Piece("Reducer", 1, c, outline, seam_length=slant)
    pc.hole = (hole_right, hole_left)

    # fold lines along generators, evenly around (not on the seam)
    if p.fold_lines:
        for i in range(p.fold_lines):
            ph = two_pi * (i + 0.5) / p.fold_lines
            a, b = cone.xy(ph, 0.0), cone.xy(ph, p.h1)
            pc.fold_lines.append((a, b))
            for mk in fold_marks_on_line(a, b, p.fold_mark_length, p.fold_mark_gap):
                if not (_in_poly(mk[0], right + [right[0]]) or _in_poly(mk[1], right + [right[0]]) or
                        _in_poly(mk[0], left + [left[0]]) or _in_poly(mk[1], left + [left[0]])):
                    pc.fold_marks.append(mk)
    for ph, lab in ((math.pi / 2, "SIDE"), (math.pi, "BACK"), (3 * math.pi / 2, "SIDE")):
        a, b = cone.xy(ph, 0.0), cone.xy(ph, p.h1)
        pc.ref_lines.append((a, b))
        pc.ref_labels.append((((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), lab))
    pc.dims = [(cone.xy(0.0, p.h1), cone.xy(0.0, 0.0), "SEAM")]
    pc.arc_lengths = (math.pi * p.d2, math.pi * p.d1)
    return pc


def _develop_branch(p, m, betas, ts, tol):
    n = len(betas) - 1
    lengths = [p.length - t for t in ts[:-1]]          # generator lengths, end -> reducer
    i_seam = min(range(n), key=lambda i: lengths[i])   # shortest generator
    width = math.pi * p.d3

    def length_at(bs):
        """Generator length at angle bs measured from the seam (exact solve)."""
        return p.length - m.meet((betas[i_seam] + bs) % (2 * math.pi))

    pts = []
    for j in range(n + 1):
        bs = 2 * math.pi * j / n
        pts.append((m.r3 * bs, length_at(bs)))
    s_len = pts[0][1]
    c = [arcs.Seg((0.0, 0.0), (width, 0.0)),                        # square branch end
         arcs.Seg((width, 0.0), (width, s_len))]                    # seam
    c += [sg.reversed() for sg in reversed(arcs.fit_points(pts, tol))]   # edge on the reducer
    c.append(arcs.Seg((0.0, s_len), (0.0, 0.0)))                    # seam
    outline = [(0.0, 0.0), (width, 0.0)] + list(reversed(pts)) + [(0.0, 0.0)]
    pc = Piece("Branch", 1, c, outline, seam_length=s_len)

    if p.fold_lines:
        for i in range(p.fold_lines):
            bs = 2 * math.pi * (i + 0.5) / p.fold_lines
            a, b = (m.r3 * bs, 0.0), (m.r3 * bs, length_at(bs))
            pc.fold_lines.append((a, b))
            pc.fold_marks += fold_marks_on_line(a, b, p.fold_mark_length, p.fold_mark_gap)
    # reference generators; the seam (shortest generator) is normally the top
    seam_top = math.cos(betas[i_seam]) >= 0
    opposite = "BOTTOM" if seam_top else "TOP"
    for bs, lab in ((math.pi / 2, "SIDE"), (math.pi, opposite), (3 * math.pi / 2, "SIDE")):
        x = m.r3 * bs
        pc.ref_lines.append(((x, 0.0), (x, length_at(bs))))
        pc.ref_labels.append(((x, 0.0), lab))
    pc.dims = [((0.0, s_len), (0.0, 0.0), "SEAM")]
    pc.longest = max(lengths)
    pc.top_beta = betas[i_seam]
    return pc


def _sampled_outline(contour):
    """Polygon through points sampled along every segment (arcs bulge past
    their end points, so the end points alone give a too-small bounding box)."""
    pts = []
    for sg in contour:
        pts += sg.sample(12)[:-1]
    return pts + [pts[0]]


def _in_poly(pt, poly):
    x, y = pt
    inside = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:]):
        if (y0 > y) != (y1 > y):
            xc = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if xc > x:
                inside = not inside
    return inside


def layout(reducer: Piece, branch: Piece, gap: float, show_reducer=True, show_branch=True):
    """Reducer at the bottom, branch above it; both start at x = 0."""
    out = []
    y = 0.0
    for pc, on in ((reducer, show_reducer), (branch, show_branch)):
        if not on:
            continue
        x0, y0, x1, y1 = pc.bbox()
        pc.offset = (-x0, y - y0)
        y += (y1 - y0) + gap
        out.append(pc)
    return out
