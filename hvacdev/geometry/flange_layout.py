# SPDX-License-Identifier: LGPL-2.1-or-later
"""Annotations for the flange. D and T (information only) are written only
when reference dimensions or annotations are switched on."""

import math

from .layout import Options, text_height
from .flange import SLOT_LENGTH


def annotations(pat, p, opts: Options):
    """(ref_lines, dim_lines, texts) in pattern coordinates."""
    th = text_height(p.a)
    cx, cy = pat.centre
    rd, ra, rb = p.d / 2, p.a / 2, p.b / 2
    ref, dim, texts = [], [], []

    if opts.reference_lines:
        # centre lines, the B circle and the slot hole centres
        ref.append(((cx - rd - th, cy), (cx + rd + th, cy)))
        ref.append(((cx, cy - rd - th), (cx, cy + rd + th)))
        n = 120
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            if i % 2 == 0:                                  # dashed look
                ref.append(((cx + rb * math.cos(a0), cy + rb * math.sin(a0)),
                            (cx + rb * math.cos(a1), cy + rb * math.sin(a1))))
        s = max(1.5, p.m * 0.25)
        for hx, hy in pat.hole_centres:                     # small crosses
            ref.append(((hx - s, hy), (hx + s, hy)))
            ref.append(((hx, hy - s), (hx, hy + s)))

    if opts.reference_dims:
        # A across the middle (horizontal), D below, B and the slot data as text
        dim.append(((cx - ra, cy), (cx + ra, cy)))
        texts.append(((cx + ra * 0.45, cy + th * 0.9), "A %.0f" % p.a, th, 0.0))
        yd = cy - rd - th * 2.5
        dim.append(((cx - rd, yd), (cx + rd, yd)))
        dim.append(((cx - rd, cy - th * 0.5), (cx - rd, yd - th * 0.6)))
        dim.append(((cx + rd, cy - th * 0.5), (cx + rd, yd - th * 0.6)))
        texts.append(((cx, yd - th * 1.0), "D %.0f" % p.d, th, 0.0))
        texts.append(((cx, cy - ra * 0.45), "B %.0f" % p.b, th * 0.8, 0.0))
        texts.append(((cx, cy - ra * 0.45 - th * 1.4),
                      "%d SLOTS  M %g x %g" % (p.n, p.m, SLOT_LENGTH), th * 0.7, 0.0))
        texts.append(((cx, cy - ra * 0.45 - th * 2.6), "E %g   T %g" % (p.e, p.t), th * 0.7, 0.0))

    if opts.piece_labels:
        y = cy + ra * 0.45
        texts.append(((cx, y), "FLANGE A%g  x1" % p.a, th, 0.0))
        texts.append(((cx, y - th * 1.5), "D %g  T %g" % (p.d, p.t), th * 0.8, 0.0))

    return ref, dim, texts
