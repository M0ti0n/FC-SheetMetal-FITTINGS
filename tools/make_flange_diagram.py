"""Generates resources/diagrams/flange.svg (task-panel parameter picture for the flange).

Top view of a flat ring flange:
    A   inner diameter
    B   bolt (slot) circle diameter
    E   ring width (inner to outer edge)
    M   slot width
    25  distance between the end-hole centres of a slot
Six arc slots on the bolt circle, each with three hole centres.
Same drawing style as the elbow / transition / branch-reducer diagrams.

    python tools/make_flange_diagram.py            writes the SVG
    python tools/make_flange_diagram.py --preview  also writes a PNG preview next to it
"""
import math
import os
import sys

W, H = 330, 316
BLACK = "#111"
BLUE = "#2a56d6"
AXIS_DASH = "7,3,2,3"
FONT_SIZE = 20

CX, CY = 165.0, 166.0
R_OUT, R_IN, R_B = 138.0, 106.0, 122.0      # outer edge, inner edge (A), bolt circle (B)
SLOT_W = 11.0                                # M
SLOT_C = 30.0                                # distance between end-hole centres ("25")
SLOTS = (90, 30, -30, -90, 150, 210)         # slot positions [deg]
B_ANGLE = 124.0                              # direction of the B dimension
E_ANGLE = 233.0                              # direction of the E dimension

prims = []


def pt(r, deg):
    a = math.radians(deg)
    return (CX + r * math.cos(a), CY - r * math.sin(a))


def line(p, q, w=1.0, color=BLACK, dash=None, end_arrow=False, both=False):
    prims.append(("line", p, q, w, color, dash, end_arrow, both))


def circle(r, w, color=BLACK, dash=None):
    prims.append(("circle", r, w, color, dash))


def text(p, s):
    prims.append(("text", p, s))


# ---- centre lines (blue dash-dot): axes and bolt circle
line((CX - R_OUT - 12, CY), (CX + R_OUT + 12, CY), 1.3, BLUE, AXIS_DASH)
line((CX, CY - R_OUT - 12), (CX, CY + R_OUT + 12), 1.3, BLUE, AXIS_DASH)
circle(R_B, 1.3, BLUE, AXIS_DASH)

# ---- flange outlines (thick)
circle(R_OUT, 2.2)
circle(R_IN, 2.2)
half = math.degrees(SLOT_C / 2 / R_B)        # half angular length of a slot (centre to centre)
for phi in SLOTS:
    prims.append(("slot", phi, half))

# ---- A: inner diameter, on the horizontal axis
line(pt(R_IN - 1.5, 180), pt(R_IN - 1.5, 0), 1.4, both=True)
text((CX + 55, CY - 9), "A")

# ---- B: bolt circle diameter, diagonal
line(pt(R_B - 1.5, B_ANGLE), pt(R_B - 1.5, B_ANGLE + 180), 1.4, both=True)
bx, by = pt(52, B_ANGLE)
nx, ny = math.sin(math.radians(B_ANGLE)), math.cos(math.radians(B_ANGLE))   # perpendicular (screen)
text((bx + nx * 14, by + ny * 14), "B")

# ---- E: ring width, arrows from outside pointing in
line(pt(R_OUT + 24, E_ANGLE), pt(R_OUT + 1, E_ANGLE), 1.4, end_arrow=True)
line(pt(R_IN - 24, E_ANGLE), pt(R_IN - 1, E_ANGLE), 1.4, end_arrow=True)
line(pt(R_IN, E_ANGLE), pt(R_OUT, E_ANGLE), 1.0)
ex, ey = pt(R_OUT + 10, E_ANGLE)
en = (math.sin(math.radians(E_ANGLE)), math.cos(math.radians(E_ANGLE)))
text((ex - en[0] * 16, ey - en[1] * 16), "E")

# ---- top slot: "25" (between end-hole centres) and M (slot width)
l_c, r_c = pt(R_B, 90 + half), pt(R_B, 90 - half)
y_dim = CY - R_IN + 20
for x, y in (l_c, r_c):
    line((x, y + 4), (x, y_dim + 5))                                   # extension lines
line((l_c[0] - 20, y_dim), (l_c[0] - 1, y_dim), 1.4, end_arrow=True)
line((r_c[0] + 20, y_dim), (r_c[0] + 1, y_dim), 1.4, end_arrow=True)
line((l_c[0], y_dim), (r_c[0], y_dim), 1.0)
text(((l_c[0] + r_c[0]) / 2, y_dim + 18), "25")

y_top, y_bot = CY - (R_B + SLOT_W / 2), CY - (R_B - SLOT_W / 2)
x_m = r_c[0] + SLOT_W / 2 + 22
for y in (y_top, y_bot):
    line((r_c[0] + SLOT_W / 2 + 4, y), (x_m + 6, y))                    # extension lines
line((x_m, y_top - 20), (x_m, y_top - 1), 1.4, end_arrow=True)
line((x_m, y_bot + 46), (x_m, y_bot + 1), 1.4, end_arrow=True)
line((x_m, y_top), (x_m, y_bot), 1.0)
text((x_m, y_bot + 62), "M")


# ------------------------------------------------------------------ SVG
def slot_path(phi, half):
    rt, rb, w = R_B + SLOT_W / 2, R_B - SLOT_W / 2, SLOT_W / 2
    o1, o2 = pt(rt, phi + half), pt(rt, phi - half)
    i2, i1 = pt(rb, phi - half), pt(rb, phi + half)
    return ("M%.2f,%.2f A%.2f,%.2f 0 0 1 %.2f,%.2f A%.2f,%.2f 0 0 1 %.2f,%.2f "
            "A%.2f,%.2f 0 0 0 %.2f,%.2f A%.2f,%.2f 0 0 1 %.2f,%.2f Z"
            % (o1[0], o1[1], rt, rt, o2[0], o2[1], w, w, i2[0], i2[1],
               rb, rb, i1[0], i1[1], w, w, o1[0], o1[1]))


def svg():
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">' % (W, H, W, H),
           '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse"><path d="M0,1 L10,5 L0,9 z" fill="%s"/></marker></defs>' % BLACK,
           '<rect width="100%" height="100%" fill="white"/>']
    for pr in prims:
        kind = pr[0]
        if kind == "line":
            _, p, q, w, color, dash, end_arrow, both = pr
            extra = ' stroke-dasharray="%s"' % dash if dash else ""
            if both:
                extra += ' marker-start="url(#ar)" marker-end="url(#ar)"'
            elif end_arrow:
                extra += ' marker-end="url(#ar)"'
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.1f"%s/>'
                       % (p[0], p[1], q[0], q[1], color, w, extra))
        elif kind == "circle":
            _, r, w, color, dash = pr
            extra = ' stroke-dasharray="%s"' % dash if dash else ""
            out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-width="%.1f"%s/>'
                       % (CX, CY, r, color, w, extra))
        elif kind == "slot":
            _, phi, half = pr
            out.append('<path d="%s" fill="none" stroke="%s" stroke-width="2.2" stroke-linejoin="round"/>'
                       % (slot_path(phi, half), BLACK))
            for d in (phi + half, phi, phi - half):
                x, y = pt(R_B, d)
                out.append('<circle cx="%.1f" cy="%.1f" r="2.4" fill="%s"/>' % (x, y, BLACK))
        elif kind == "text":
            _, p, s = pr
            out.append('<text x="%.1f" y="%.1f" font-family="Arial" font-size="%d" font-weight="bold" '
                       'fill="%s" text-anchor="middle">%s</text>' % (p[0], p[1] + 7, FONT_SIZE, BLACK, s))
    out.append("</svg>")
    return "\n".join(out)


def preview(path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle
    fig, ax = plt.subplots(figsize=(W / 60, H / 60))
    ls = lambda d: (0, (7, 3, 2, 3)) if d else "-"
    for pr in prims:
        kind = pr[0]
        if kind == "line":
            _, p, q, w, color, dash, end_arrow, both = pr
            ax.plot([p[0], q[0]], [p[1], q[1]], color=color, lw=w * 0.75, ls=ls(dash))
            heads = [(p, q)] if end_arrow else ([(p, q), (q, p)] if both else [])
            for a, b in heads:
                ax.annotate("", xy=b, xytext=(a[0] + (b[0] - a[0]) * 0.8, a[1] + (b[1] - a[1]) * 0.8),
                            arrowprops=dict(arrowstyle="-|>", color="k", lw=0, mutation_scale=9))
        elif kind == "circle":
            _, r, w, color, dash = pr
            ax.add_patch(Circle((CX, CY), r, fill=False, color=color, lw=w * 0.75, ls=ls(dash)))
        elif kind == "slot":
            _, phi, half = pr
            rt, rb, w = R_B + SLOT_W / 2, R_B - SLOT_W / 2, SLOT_W / 2
            def cap(center_deg, sign):           # half circle around an end-hole centre
                cx, cy = pt(R_B, center_deg)
                base = math.atan2(-(cy - CY), cx - CX)          # radial direction (y up)
                return [(cx + w * math.cos(base + sign * math.pi * k / 20),
                         cy - w * math.sin(base + sign * math.pi * k / 20)) for k in range(21)]
            pts = [pt(rt, phi + half - 2 * half * i / 30) for i in range(31)]   # outer arc
            pts += cap(phi - half, -1)                                          # end cap
            pts += [pt(rb, phi - half + 2 * half * i / 30) for i in range(31)]  # inner arc
            pts += list(reversed(cap(phi + half, 1)))                           # start cap
            xs, ys = zip(*(pts + [pts[0]]))
            ax.plot(xs, ys, "k", lw=1.6)
            for d in (phi + half, phi, phi - half):
                x, y = pt(R_B, d)
                ax.add_patch(Circle((x, y), 2.4, color="k"))
        elif kind == "text":
            _, p, s = pr
            ax.text(p[0], p[1], s, fontsize=FONT_SIZE * 0.62, weight="bold", ha="center", va="center")
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(path, dpi=110, bbox_inches="tight", facecolor="white")


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "resources", "diagrams", "flange.svg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(svg())
    print("wrote", out)
    if "--preview" in sys.argv:
        png = sys.argv[sys.argv.index("--preview") + 1] if len(sys.argv) > sys.argv.index("--preview") + 1 \
            else out.replace(".svg", "_preview.png")
        preview(png)
        print("wrote", png)
