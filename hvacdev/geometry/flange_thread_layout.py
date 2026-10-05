# SPDX-License-Identifier: LGPL-2.1-or-later
"""Annotations for the threaded flange. D and T (information only) are written
only when reference dimensions or annotations are switched on."""

import math

from .layout import Options, text_height
from .flange_thread import tap_drill


def annotations(pat, p, opts: Options):
    """(ref_lines, dim_lines, texts) in pattern coordinates."""
    th = text_height(p.a)
    cx, cy = pat.centre
    rd, ra, rb = p.d / 2, p.a / 2, p.b / 2
    ref, dim, texts = [], [], []

    if opts.reference_lines:
        ref.append(((cx - rd - th, cy), (cx + rd + th, cy)))
        ref.append(((cx, cy - rd - th), (cx, cy + rd + th)))
        n = 120
        for i in range(0, n, 2):                            # B circle, dashed look
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            ref.append(((cx + rb * math.cos(a0), cy + rb * math.sin(a0)),
                        (cx + rb * math.cos(a1), cy + rb * math.sin(a1))))

    if opts.reference_dims:
        dim.append(((cx - ra, cy), (cx + ra, cy)))
        texts.append(((cx + ra * 0.45, cy + th * 0.9), "A %g" % p.a, th, 0.0))
        yd = cy - rd - th * 2.5
        dim.append(((cx - rd, yd), (cx + rd, yd)))
        dim.append(((cx - rd, cy - th * 0.5), (cx - rd, yd - th * 0.6)))
        dim.append(((cx + rd, cy - th * 0.5), (cx + rd, yd - th * 0.6)))
        texts.append(((cx, yd - th * 1.0), "D %g" % p.d, th, 0.0))
        texts.append(((cx, cy - ra * 0.45), "B %g" % p.b, th * 0.8, 0.0))
        texts.append(((cx, cy - ra * 0.45 - th * 1.4),
                      "%d x %s  (TAP DRILL %g)" % (p.n, p.m.upper(), tap_drill(p.m)), th * 0.7, 0.0))
        texts.append(((cx, cy - ra * 0.45 - th * 2.6), "E %g   T %g" % (p.e, p.t), th * 0.7, 0.0))

    if opts.piece_labels:
        y = cy + ra * 0.45
        texts.append(((cx, y), "FLANGE %s A%g  x1" % (p.m.upper(), p.a), th, 0.0))
        texts.append(((cx, y - th * 1.5), "D %g  T %g" % (p.d, p.t), th * 0.8, 0.0))

    return ref, dim, texts
