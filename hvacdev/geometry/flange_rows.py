# SPDX-License-Identifier: LGPL-2.1-or-later
"""Combined / Divided output for both flange tools.

Bottom row: the whole flange (Combined). Row above: the sections (Divided),
each turned with its middle pointing up, side by side.
"""

from dataclasses import dataclass, field
from typing import List, Tuple

from . import flange_divide as fd
from .layout import text_height


@dataclass
class FlangeRows:
    contours: list = field(default_factory=list)          # arcs.Seg chains, sheet coordinates
    marks: List[Tuple] = field(default_factory=list)      # mark lines, sheet coordinates
    ref: List[Tuple] = field(default_factory=list)
    dim: List[Tuple] = field(default_factory=list)
    texts: List[Tuple] = field(default_factory=list)
    sections: str = ""                                     # e.g. "Section A x2 (108 deg, 3 holes), ..."
    divided: bool = False


def _shift(q, off):
    return (q[0] + off[0], q[1] + off[1])


def build(p, pat, whole_annotations, hole_contours, hole_marks, hole_centre,
          show_combined: bool, show_divided: bool, label_sections: bool, hole_word: str) -> FlangeRows:
    """p / pat: flange parameters and developed pattern (either flange tool).
    whole_annotations: (ref, dim, texts) of the whole flange.
    hole_contours(k) / hole_marks(k) / hole_centre(k): features of hole k."""
    out = FlangeRows()
    if show_combined:
        out.contours += pat.contours
        out.marks += [m for k in range(p.n) for m in hole_marks(k)]
        r, d, t = whole_annotations
        out.ref += r
        out.dim += d
        out.texts += t

    out.divided = show_divided and fd.can_divide(p.a, p.n)
    if not out.divided:
        return out
    pieces = fd.make_pieces(pat.centre, p.a / 2, p.d / 2, p.n, p.start_angle,
                            hole_contours, hole_marks, hole_centre)
    gap = max(30.0, 0.08 * p.d)
    fd.layout_rows(p.d, pieces, show_combined, gap)
    th = text_height(p.a)
    desc = []
    for pc in pieces:
        off = pc.offset
        out.contours += [[s.mapped(lambda q, off=off: _shift(q, off)) for s in cn] for cn in pc.contours]
        out.marks += [(_shift(a, off), _shift(b, off)) for a, b in pc.marks]
        desc.append("%s x%d (%g deg, %d %s)" % (pc.name, pc.quantity, round(pc.span, 3), pc.holes, hole_word))
        if label_sections:
            x, y = _shift(pc.label_pos, off)
            out.texts.append(((x, y), "%s  x%d" % (pc.name.upper(), pc.quantity), th, 0.0))
            out.texts.append(((x, y - th * 1.4), "%g DEG  %d %s" % (round(pc.span, 2), pc.holes,
                                                                    hole_word.upper()), th * 0.7, 0.0))
    out.sections = ", ".join(desc)
    return out
