# SPDX-License-Identifier: LGPL-2.1-or-later
"""Annotations for the transition pattern (same options as the elbow)."""

import math

from .layout import Options, text_height


def _readable(angle_deg):
    """Keep text upright: angle in (-90, 90]."""
    a = (angle_deg + 180.0) % 360.0 - 180.0
    if a > 90.0:
        a -= 180.0
    elif a <= -90.0:
        a += 180.0
    return a


def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    return dx / L, dy / L, L


def annotations(pat, opts: Options, params_text: str, size_ref: float):
    """Returns (ref_lines, dim_lines, texts) in pattern coordinates."""
    th = text_height(size_ref)
    ref, dim, texts = [], [], []

    if opts.fold_lines and opts.fold_labels:
        for i, (a, b) in enumerate(pat.fold_lines, 1):
            ux, uy, _ = _unit(a, b)
            pos = (b[0] + ux * th * 0.8, b[1] + uy * th * 0.8)
            ang = math.degrees(math.atan2(uy, ux))
            if _readable(ang) != (ang + 180.0) % 360.0 - 180.0:
                # text flipped to stay readable -> start it further out
                pos = (b[0] + ux * th * 2.6, b[1] + uy * th * 2.6)
            texts.append((pos, "F%d" % i, th * 0.6, _readable(ang)))
        x0, y0, _, _ = pat.bbox()
        texts.append(((x0, y0 - th * 1.6), "FOLDS: %d" % len(pat.fold_lines), th * 0.7, 0.0))

    if opts.reference_dims:
        # straight rectangle edges: length written outside, along the edge
        for a, b, name in pat.bottom_edges:
            ux, uy, L = _unit(a, b)
            nx, ny = uy, -ux                      # outward (pattern lies left of a -> b)
            mid = ((a[0] + b[0]) / 2 + nx * th * 1.2, (a[1] + b[1]) / 2 + ny * th * 1.2)
            texts.append((mid, "%s %.1f" % (name, L), th * 0.6, _readable(math.degrees(math.atan2(uy, ux)))))
        # seam length (left seam edge)
        seam = pat.contour[-1]
        ux, uy, L = _unit(seam.start, seam.end)
        mid = ((seam.start[0] + seam.end[0]) / 2 - th * 1.2, (seam.start[1] + seam.end[1]) / 2)
        texts.append((mid, "SEAM %.1f" % L, th * 0.6, 90.0))

    if opts.reference_lines:
        ref = list(pat.fold_lines)                # full triangulation lines

    if opts.piece_labels and pat.fold_lines:
        a, b = pat.fold_lines[len(pat.fold_lines) // 2]
        c = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        texts.append(((c[0], c[1] + th * 0.8), "%s  x%d" % (pat.name.upper(), pat.quantity), th, 0.0))
        texts.append(((c[0], c[1] - th * 0.8), params_text, th * 0.7, 0.0))

    return ref, dim, texts
