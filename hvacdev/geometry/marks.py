# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press-brake fold marks on an arbitrary straight fold line."""
import math


MIN_MARK = 0.5        # marks shorter than this are left out [mm]


def fold_marks_on_line(p0, p1, length=15.0, gap=2.0, ends="both"):
    """Marks of `length`, starting `gap` inside the ends of the fold line
    p0 -> p1. ends = "both" (a mark at each end), "end" (only at p1).
    If the line is too short for two marks they merge into one mark that
    still keeps the gaps; nothing if even that does not fit."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    if L <= 2 * gap + MIN_MARK:
        return []
    ux, uy = dx / L, dy / L

    def at(t):
        return (p0[0] + ux * t, p0[1] + uy * t)

    if ends == "end":
        return [(at(max(gap, L - gap - length)), at(L - gap))]
    if 2 * (gap + length) >= L:
        return [(at(gap), at(L - gap))]
    return [(at(gap), at(gap + length)), (at(L - gap - length), at(L - gap))]
