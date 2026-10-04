# SPDX-License-Identifier: LGPL-2.1-or-later
"""Places developed sections on the sheet and builds the annotation set.

The same Drawing is used for the FreeCAD model space AND for the DXF, so
what you preview in FreeCAD is exactly what gets exported.
"""

from dataclasses import dataclass, field
from typing import List, Tuple

Point = Tuple[float, float]


@dataclass
class Options:
    fold_lines: bool = True          # "Add folding lines"
    reference_dims: bool = False     # "Add reference dimensions"
    fold_labels: bool = False        # "Add folding labels"
    reference_lines: bool = False    # "Add annotations": heel/throat/side + mid-plane lines
    piece_labels: bool = False       # "Add annotations": name, quantity, D/A/R


@dataclass
class PlacedSection:
    key: str                          # "middle" / "end"
    title: str
    quantity: int
    offset: Point
    cut: list = field(default_factory=list)          # arcs.Seg chain (lines + arcs)
    fold: List[Tuple[Point, Point]] = field(default_factory=list)
    ref: List[Tuple[Point, Point]] = field(default_factory=list)
    dim: List[Tuple[Point, Point]] = field(default_factory=list)
    text: List[Tuple[Point, str, float, float]] = field(default_factory=list)  # pos, str, h, rot


def text_height(diameter: float) -> float:
    return max(8.0, min(40.0, diameter / 25.0))


def _shift(pts, dx, dy):
    return [(x + dx, y + dy) for x, y in pts]


def _shift_seg(seg, dx, dy):
    (x1, y1), (x2, y2) = seg
    return ((x1 + dx, y1 + dy), (x2 + dx, y2 + dy))


def _generator_length(section, x):
    """Length of the reference generator at x (heel / throat)."""
    for (ax, ay), (bx, by) in section.reference_lines:
        if abs(ax - x) < 1e-9 and abs(bx - x) < 1e-9:
            return abs(by - ay)
    return 0.0


def place(section, key, offset, opts: Options, params_text: str, diameter: float):
    dx, dy = offset
    th = text_height(diameter)
    ps = PlacedSection(key, section.name, section.quantity, offset,
                       cut=[sg.mapped(lambda q: (q[0] + dx, q[1] + dy)) for sg in section.contour])

    if opts.fold_lines:
        ps.fold = [_shift_seg(s, dx, dy) for s in section.fold_marks]
        if opts.fold_labels:
            for i, ((x, y1), (_, y2)) in enumerate(section.fold_lines, 1):
                top = max(y1, y2)
                ps.text.append(((x + dx, top + dy + th * 0.6), "F%d" % i, th * 0.6, 90.0))
            if section.fold_lines:
                x0, y0, x1, y1 = section.bbox()
                ps.text.append(((x0 + dx, y0 + dy - th * 1.6),
                                "FOLDS: %d x %.2f deg" % (len(section.fold_lines), section.fold_angle),
                                th * 0.7, 0.0))

    if opts.reference_lines:
        ps.ref = [_shift_seg(s, dx, dy) for s in section.reference_lines]
        for (x, y), label in section.reference_labels:
            if opts.reference_dims and label in ("HEEL", "THROAT"):
                label = "%s %.1f" % (label, _generator_length(section, x))
            ps.text.append(((x + dx + th * 0.3, y + dy + th * 0.3), label, th * 0.5, 90.0))

    x0, y0, x1, y1 = section.bbox()
    if opts.piece_labels:
        cx = (x0 + x1) / 2 + dx
        cy = (y0 + y1) / 2 + dy
        ps.text.append(((cx, cy + th * 0.8), "%s  x%d" % (section.name.upper(), section.quantity), th, 0.0))
        ps.text.append(((cx, cy - th * 0.8), params_text, th * 0.7, 0.0))

    if opts.reference_dims:
        # developed length below the pattern
        yd = y0 - th * 3.2
        ps.dim.append(((x0 + dx, yd + dy), (x1 + dx, yd + dy)))
        ps.dim.append(((x0 + dx, y0 + dy - th * 0.4), (x0 + dx, yd + dy - th * 0.4)))
        ps.dim.append(((x1 + dx, y0 + dy - th * 0.4), (x1 + dx, yd + dy - th * 0.4)))
        ps.text.append((((x0 + x1) / 2 + dx, yd + dy + th * 0.3),
                        "%.1f" % (x1 - x0), th * 0.8, 0.0))
        # seam edge length: dimension line just outside the left edge
        ys = [y for x, y in section.outline if abs(x - x0) < 1e-9]
        e0, e1 = min(ys), max(ys)
        xd = x0 - th * 1.5
        ps.dim.append(((xd + dx, e0 + dy), (xd + dx, e1 + dy)))
        ps.dim.append(((x0 + dx - th * 0.3, e0 + dy), (xd + dx - th * 0.4, e0 + dy)))
        ps.dim.append(((x0 + dx - th * 0.3, e1 + dy), (xd + dx - th * 0.4, e1 + dy)))
        ps.text.append(((xd + dx - th * 0.3, (e0 + e1) / 2 + dy), "%.1f" % (e1 - e0), th * 0.7, 90.0))
    return ps


def offsets(middle, end, diameter, include_middle=True, include_end=True):
    """Sheet offsets: end section at the bottom (square edge on y = 0),
    middle section stacked above it."""
    th = text_height(diameter)
    gap = max(6 * th, 0.15 * diameter)
    out = {}
    y_cursor = 0.0
    if include_end:
        out["end"] = (0.0, 0.0)
        y_cursor = end.h_max + gap
    if include_middle:
        out["middle"] = (0.0, y_cursor + middle.h_max)
    return out


def build(middle, end, opts: Options, params_text: str, diameter: float,
          include_middle=True, include_end=True) -> List[PlacedSection]:
    """Local geometry (x, y from the section's own origin) + sheet offset."""
    placed = []
    offs = offsets(middle, end, diameter, include_middle, include_end)
    for key, sec in (("end", end), ("middle", middle)):
        if key in offs and sec.quantity > 0:
            ps = place(sec, key, (0.0, 0.0), opts, params_text, diameter)
            ps.offset = offs[key]
            placed.append(ps)
    return placed


def write_dxf(placed: List[PlacedSection], path: str):
    """Write placed sections (local geometry + offset) to an R12 DXF."""
    from ..dxf.writer import DxfWriter
    w = DxfWriter()
    for ps in placed:
        dx, dy = ps.offset
        w.contour([sg.mapped(lambda q: (q[0] + dx, q[1] + dy)) for sg in ps.cut], "CUT")
        for seg in ps.fold:
            w.line(*_shift_seg(seg, dx, dy), "FOLD")
        for seg in ps.ref:
            w.line(*_shift_seg(seg, dx, dy), "REF")
        for seg in ps.dim:
            w.line(*_shift_seg(seg, dx, dy), "DIM")
        for (x, y), s, h, rot in ps.text:
            w.text((x + dx, y + dy), s, h, rotation=rot, center=(rot == 0.0))
    w.save(path)
