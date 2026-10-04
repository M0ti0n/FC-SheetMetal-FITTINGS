# SPDX-License-Identifier: LGPL-2.1-or-later
"""Annotations for the reducer-with-branch pieces (same options as the other tools)."""

import math

from .layout import Options, text_height
from .transition_layout import _readable, _unit


def annotations(pc, opts: Options, params_text: str, size_ref: float):
    """(ref_lines, dim_lines, texts) in piece coordinates."""
    th = text_height(size_ref)
    ref, dim, texts = [], [], []

    if opts.fold_lines and opts.fold_labels and pc.fold_lines:
        for i, (a, b) in enumerate(pc.fold_lines, 1):
            ux, uy, _ = _unit(a, b)
            pos = (b[0] + ux * th * 0.8, b[1] + uy * th * 0.8)
            texts.append((pos, "F%d" % i, th * 0.6, _readable(math.degrees(math.atan2(uy, ux)))))
        x0, y0, _, _ = pc.bbox()
        texts.append(((x0, y0 - th * 1.6), "FOLDS: %d" % len(pc.fold_lines), th * 0.7, 0.0))

    if opts.reference_dims:
        for a, b, name in pc.dims:                      # seam edge, written outside
            ux, uy, L = _unit(a, b)
            nx, ny = uy, -ux
            mid = ((a[0] + b[0]) / 2 + nx * th * 1.2, (a[1] + b[1]) / 2 + ny * th * 1.2)
            texts.append((mid, "%s %.1f" % (name, L), th * 0.6,
                          _readable(math.degrees(math.atan2(uy, ux)))))
        x0, y0, x1, y1 = pc.bbox()
        if pc.name == "Reducer":
            d2, d1 = pc.arc_lengths
            texts.append((((x0 + x1) / 2, y0 - th * 1.6), "BOTTOM EDGE %.1f / TOP EDGE %.1f" % (d2, d1),
                          th * 0.6, 0.0))
        else:
            texts.append((((x0 + x1) / 2, y0 - th * 1.2), "%.1f" % (x1 - x0), th * 0.7, 0.0))
            texts.append((((x0 + x1) / 2, y0 - th * 2.4), "LONGEST %.1f" % pc.longest, th * 0.6, 0.0))

    if opts.reference_lines:
        ref = list(pc.ref_lines)
        for (x, y), lab in pc.ref_labels:
            texts.append(((x + th * 0.3, y + th * 0.3), lab, th * 0.5, 90.0))

    if opts.piece_labels:
        if pc.name == "Reducer":
            a, b = pc.ref_lines[1]                       # the BACK generator, middle of the piece
            c = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        else:
            x0, y0, x1, y1 = pc.bbox()
            c = ((x0 + x1) / 2, pc.seam_length / 2)
        texts.append(((c[0], c[1] + th * 0.8), "%s  x%d" % (pc.name.upper(), pc.quantity), th, 0.0))
        texts.append(((c[0], c[1] - th * 0.8), params_text, th * 0.7, 0.0))

    return ref, dim, texts
