# SPDX-License-Identifier: LGPL-2.1-or-later
"""Annotations for the screw flight blank."""

import math

from .layout import Options, text_height


def annotations(blank, p, opts: Options):
    """(ref_lines, dim_lines, texts) in blank coordinates."""
    r = blank.result
    th = text_height(p.od)
    cx, cy = blank.centre
    ref, dim, texts = [], [], []

    def P(rad, deg):
        a = math.radians(deg)
        return (cx + rad * math.cos(a), cy + rad * math.sin(a))

    if opts.reference_lines:
        ref.append(((cx - r.ro - th, cy), (cx + r.ro + th, cy)))
        ref.append(((cx, cy - r.ro - th), (cx, cy + r.ro + th)))
        ref.append(blank.calc_end)                 # end of the calculated part (start of the extension)
        mid_ext = blank.a_start + r.calc_angle + r.extension / 2
        x, y = P((r.ri + r.ro) / 2, mid_ext)
        texts.append(((x, y), "EXT %.2f DEG" % r.extension, th * 0.6, 0.0))

    if opts.reference_dims:
        # Ri and Ro along the horizontal axis, gap and angles as text
        dim.append(((cx, cy), P(r.ri, 0.0)))
        dim.append(((cx, cy + th * 1.6), (cx + r.ro, cy + th * 1.6)))
        texts.append(((cx + r.ri / 2, cy - th * 0.9), "Ri %.2f" % r.ri, th * 0.7, 0.0))
        texts.append(((cx + r.ro / 2, cy + th * 2.4), "Ro %.2f" % r.ro, th * 0.7, 0.0))
        texts.append(((cx, cy - r.ri * 0.35), "BLANK %.2f DEG" % r.blank_angle, th * 0.7, 0.0))
        texts.append(((cx, cy - r.ri * 0.35 - th * 1.2),
                      "CALC %.2f + EXT %.2f DEG" % (r.calc_angle, r.extension), th * 0.6, 0.0))
        texts.append(((cx, cy - r.ri * 0.35 - th * 2.4),
                      "GAP %g (INNER) / %.1f (OUTER)" % (p.gap, r.gap_outer), th * 0.6, 0.0))

    if opts.piece_labels:
        texts.append(((cx, cy + r.ri * 0.45), "SCREW FLIGHT  x%d" % r.pieces, th, 0.0))
        texts.append(((cx, cy + r.ri * 0.45 - th * 1.4),
                      "OD %g ID %g P %g L %g" % (p.od, p.id, p.pitch, p.length), th * 0.6, 0.0))
    return ref, dim, texts
