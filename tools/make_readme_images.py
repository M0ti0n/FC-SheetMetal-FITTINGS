"""Flat-pattern pictures and the toolbar strip for the README (docs/images/).

    python tools/make_readme_images.py

Uses the real development code with each tool's default values:
cut contour black, fold / drill marks red, annotations off.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

from hvacdev.geometry import elbow as eg, layout as lay, transition as tg, branch_reducer as bg  # noqa: E402
from hvacdev.geometry import flange as fg, flange_thread as ftg, flange_divide as fd, screw as sg  # noqa: E402

OUT = os.path.join(ROOT, "docs", "images")
CUT, MARK = "#111111", "#d22020"


def draw(pieces, path, w=6.0):
    """pieces: list of (contours, marks, offset)."""
    fig, ax = plt.subplots(figsize=(w, w))
    for contours, marks, (dx, dy) in pieces:
        for c in contours:
            pts = [q for s in c for q in s.sample(24)]
            ax.plot([p[0] + dx for p in pts], [p[1] + dy for p in pts], color=CUT, lw=1.3)
        for a, b in marks:
            ax.plot([a[0] + dx, b[0] + dx], [a[1] + dy, b[1] + dy], color=MARK, lw=1.0)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(path, dpi=120, bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(fig)
    print("wrote", os.path.relpath(path, ROOT))


def elbow():
    p = eg.ElbowParams()
    m, e = eg.develop(p)
    offs = lay.offsets(m, e, p.diameter)
    return [([e.contour], e.fold_marks, offs["end"]), ([m.contour], m.fold_marks, offs["middle"])]


def transition():
    p = tg.TransitionParams()
    pcs = tg.develop_selection(p, combined=True, short=True, long_=True)
    return [([pc.contour], pc.fold_marks, pc.offset) for pc in pcs]


def branch():
    p = bg.BranchReducerParams()
    r, b = bg.develop(p)
    bg.layout(r, b, max(60.0, 0.15 * p.d2))
    return [([pc.contour], pc.fold_marks, pc.offset) for pc in (r, b)]


def flange():
    p, _ = fg.params_for(400)
    pat = fg.develop(p)
    pcs = fd.make_pieces(pat.centre, p.a / 2, p.d / 2, p.n, p.start_angle,
                         lambda k: [pat.slots[k]], lambda k: [], lambda k: pat.hole_centres[3 * k + 1])
    fd.layout_rows(p.d, pcs, True, max(30.0, 0.08 * p.d))
    return [(pat.contours, [], (0.0, 0.0))] + [(pc.contours, [], pc.offset) for pc in pcs]


def thread_flange():
    p, _ = ftg.params_for(400)
    pat = ftg.develop(p)
    pcs = fd.make_pieces(pat.centre, p.a / 2, p.d / 2, p.n, p.start_angle,
                         lambda k: [], lambda k: pat.marks[2 * k: 2 * k + 2], lambda k: pat.hole_centres[k])
    fd.layout_rows(p.d, pcs, True, max(30.0, 0.08 * p.d))
    return [(pat.contours, pat.marks, (0.0, 0.0))] + [(pc.contours, pc.marks, pc.offset) for pc in pcs]


def screw():
    b = sg.develop(sg.ScrewParams())
    return [([b.contour], [], (0.0, 0.0))]


def toolbar():
    names = ["SegmentedElbow", "RectRoundTransition", "BranchReducer", "Flange", "ThreadFlange", "ScrewFlight"]
    size, pad = 64, 14
    img = Image.new("RGBA", (len(names) * (size + pad) + pad, size + 2 * pad), (246, 246, 246, 255))
    for i, n in enumerate(names):
        icon = Image.open(os.path.join(ROOT, "resources", "icons", "png", "%s_blue_256.png" % n))
        icon = icon.resize((size, size), Image.LANCZOS)
        img.paste(icon, (pad + i * (size + pad), pad), icon)
    path = os.path.join(OUT, "toolbar.png")
    img.save(path)
    print("wrote", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for key, fn in (("elbow", elbow), ("transition", transition), ("branch_reducer", branch),
                    ("flange", flange), ("thread_flange", thread_flange), ("screw", screw)):
        draw(fn(), os.path.join(OUT, "%s_pattern.png" % key))
    toolbar()
