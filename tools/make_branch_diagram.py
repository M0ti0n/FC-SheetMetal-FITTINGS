"""Generates resources/diagrams/reducer_branch.svg
(task-panel parameter picture for the reducer with branch).

Side view: reducer (cone) from D2 at the bottom to D1 at the top, height H1;
a round branch D3 leaves the cone side at angle A to the horizontal. The
branch axis meets the cone side at height H2; L runs along the branch axis
from that point to the branch end.
Same drawing style as the elbow / transition diagrams.
Run:  python tools/make_branch_diagram.py
"""
import math
import os

W, H = 330, 290
BLACK = "#111"
BLUE = "#2a56d6"
AXIS_DASH = "7,3,2,3"
FONT = 'font-family="Arial" font-size="20" font-weight="bold" fill="%s"' % BLACK

# model (mm-like units, y up), proportions of the reference sketch
D1, D2, H1 = 170.0, 407.0, 392.0
H2, D3, L = 196.0, 153.0, 216.0
A = math.radians(31.0)

# ---- geometry (y up, origin = bottom centre of the cone)
xl0, xl1 = -D2 / 2, -D1 / 2                  # left cone side: (xl0, 0) -> (xl1, H1)


def cone_left_x(y):
    return xl0 + (xl1 - xl0) * y / H1


P = (cone_left_x(H2), H2)                     # branch axis meets the cone side
u = (-math.cos(A), math.sin(A))               # along the branch, outwards
n = (math.sin(A), math.cos(A))                # normal, towards the upper outline
r3 = D3 / 2
E = (P[0] + L * u[0], P[1] + L * u[1])        # centre of the branch end


def add(p, v, k=1.0):
    return (p[0] + v[0] * k, p[1] + v[1] * k)


def hit_cone(p0, d):
    """Intersection of the line p0 + t*d with the left cone side."""
    a0, a1 = (xl0, 0.0), (xl1, H1)
    ex, ey = a1[0] - a0[0], a1[1] - a0[1]
    den = d[0] * ey - d[1] * ex
    t = ((a0[0] - p0[0]) * ey - (a0[1] - p0[1]) * ex) / den
    return add(p0, d, t)


up_end, lo_end = add(E, n, r3), add(E, n, -r3)
back = (-u[0], -u[1])
up_hit, lo_hit = hit_cone(up_end, back), hit_cone(lo_end, back)
# branch axis meets the baseline (centre of the A arc)
X = (P[0] + (0.0 - P[1]) / u[1] * u[0], 0.0)

# A arc: centred where the branch axis meets the baseline, ending on the branch
# axis between the cone and the branch end (as in the reference sketch)
Q = add(P, u, 0.55 * L)
Ra = math.hypot(Q[0] - X[0], Q[1] - X[1])

# ---- fit everything that is drawn (incl. dimension space) into the picture
far = add(E, u, 125.0)                          # D3 dimension + label beyond the branch end
pts = [(xl0, -125.0), (-xl0 + 95.0, 0.0), (xl1, H1 + 115.0), (-xl1, H1 + 115.0),
       add(far, n, r3 + 10), add(far, n, -r3 - 10), add(up_end, n, 10), add(lo_end, n, -10),
       (X[0] - Ra - 25.0, 0.0)]
mx, my = 6.0, 6.0
s = min((W - 2 * mx) / (max(p[0] for p in pts) - min(p[0] for p in pts)),
        (H - 2 * my) / (max(p[1] for p in pts) - min(p[1] for p in pts)))
ox = mx - s * min(p[0] for p in pts) + (W - 2 * mx - s * (max(p[0] for p in pts) - min(p[0] for p in pts))) / 2
oy = H - my + s * min(p[1] for p in pts) - (H - 2 * my - s * (max(p[1] for p in pts) - min(p[1] for p in pts))) / 2


def S(p):
    return (ox + s * p[0], oy - s * p[1])


out = []
out.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">' % (W, H, W, H))
out.append('<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse"><path d="M0,1 L10,5 L0,9 z" fill="%s"/></marker></defs>' % BLACK)
out.append('<rect width="100%" height="100%" fill="white"/>')


def line(p, q, width=1.0, color=BLACK, dash=None, arrows=False):
    a, b = S(p), S(q)
    extra = ' stroke-dasharray="%s"' % dash if dash else ""
    if arrows:
        extra += ' marker-start="url(#ar)" marker-end="url(#ar)"'
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.1f"%s/>'
               % (a[0], a[1], b[0], b[1], color, width, extra))


def axis(p, q):
    line(p, q, 1.3, BLUE, AXIS_DASH)


def label(p, text, dx=0.0, dy=0.0):
    x, y = S(p)
    out.append('<text x="%.1f" y="%.1f" %s text-anchor="middle">%s</text>' % (x + dx, y + dy + 7, FONT, text))


def dim(p, q, text, off, lab_dx=0.0, lab_dy=0.0):
    """Dimension p -> q with the dimension line shifted by vector `off` (model units)."""
    a, b = add(p, off), add(q, off)
    L_ = math.hypot(off[0], off[1]) or 1.0
    ux, uy = off[0] / L_, off[1] / L_
    gap, over = 4 / s, 5 / s
    line(add(p, (ux * gap, uy * gap)), add(a, (ux * over, uy * over)))     # extension lines
    line(add(q, (ux * gap, uy * gap)), add(b, (ux * over, uy * over)))
    line(a, b, 1.4, arrows=True)
    label(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), text, lab_dx, lab_dy)


u_s = 1.0 / s     # one picture pixel in model units

# axes: main (vertical), baseline (horizontal, needed for A), branch axis
axis((0.0, -26 * u_s), (0.0, H1 + 18 * u_s))
axis((X[0] - Ra - 12 * u_s, 0.0), (-xl0 + 14 * u_s, 0.0))
axis(add(E, u, 14 * u_s), (0.0, P[1] + P[0] * math.tan(A)))   # to the main axis

# cone outline (thick); the left side is hidden behind the branch between the two hits
lw = 2.2
line((xl0, 0.0), (-xl0, 0.0), lw)
line((xl1, H1), (-xl1, H1), lw)
line((-xl0, 0.0), (-xl1, H1), lw)
line((xl0, 0.0), lo_hit, lw)
line(up_hit, (xl1, H1), lw)
line(lo_hit, up_hit, 1.1, BLACK, "5,3")

# branch outline (thick)
line(up_end, up_hit, lw)
line(lo_end, lo_hit, lw)
line(up_end, lo_end, lw)

# ---- dimensions
dim((xl1, H1), (-xl1, H1), "D1", (0.0, 30 * u_s), lab_dy=-12)
dim((xl0, 0.0), (-xl0, 0.0), "D2", (0.0, -30 * u_s), lab_dy=14)
dim((-xl0, 0.0), (-xl0 + (xl0 - xl1) * 0, H1), "H1", (34 * u_s, 0.0), lab_dx=-14)
# H2: from the baseline up to P, just right of P
xh2 = P[0] + 28 * u_s
line(P, (xh2 + 5 * u_s, P[1]))
line((xh2, 2 * u_s), (xh2, P[1] - 2 * u_s), 1.4, arrows=True)
label((xh2, P[1] / 2), "H2", -15)
# D3: across the branch end, outside
dim(up_end, lo_end, "D3", add((0, 0), u, 24 * u_s), lab_dx=-14, lab_dy=-4)
# L: along the branch axis from P to the end, between axis and upper outline
off = (n[0] * r3 * 0.5, n[1] * r3 * 0.5)
a_, b_ = add(P, off), add(E, off)
line(P, add(a_, n, 4 * u_s))                                 # extension at P (perpendicular)
line(a_, b_, 1.4, arrows=True)
# letter centred on the dimension line, on a small white backing, so it stays clear
# of the branch outline above and the axis below
lx, ly = S(((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2))
out.append('<rect x="%.1f" y="%.1f" width="16" height="18" fill="white"/>' % (lx - 8, ly - 9))
out.append('<text x="%.1f" y="%.1f" %s text-anchor="middle">L</text>' % (lx, ly + 7, FONT))

# A: arc centred where the branch axis meets the baseline, from the baseline to the axis
p0 = (X[0] - Ra, 0.0)
p1 = (X[0] + Ra * u[0], X[1] + Ra * u[1])
a0, a1 = S(p0), S(p1)
out.append('<path d="M%.1f,%.1f A%.1f,%.1f 0 0 1 %.1f,%.1f" fill="none" stroke="%s" stroke-width="1.4" '
           'marker-start="url(#ar)" marker-end="url(#ar)"/>' % (a0[0], a0[1], Ra * s, Ra * s, a1[0], a1[1], BLACK))
am = (X[0] + Ra * math.cos(math.pi - A / 2), Ra * math.sin(math.pi - A / 2))
label(am, "A", -14, 0)

out.append("</svg>")
path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "resources", "diagrams", "reducer_branch.svg")
os.makedirs(os.path.dirname(path), exist_ok=True)
open(path, "w").write("\n".join(out))
print("wrote", path)
