"""Generates resources/diagrams/screw.svg (task-panel picture for the screw flight).

Side view of a screw: shaft (ID), helical flight (OD), pitch P, screw length L.
Same drawing style as the other diagrams.

    python tools/make_screw_diagram.py
"""
import math
import os

W, H = 350, 270
BLACK = "#111"
BLUE = "#2a56d6"
AXIS_DASH = "7,3,2,3"
FONT = 'font-family="Arial" font-size="20" font-weight="bold" fill="%s"' % BLACK

CY = 104.0                  # screw axis
R_OUT, R_IN = 78.0, 27.0    # flight / shaft radius [px]
X0, X1 = 16.0, 252.0        # screw from X0 to X1 (L)
P = 132.0                   # pitch [px]
PHASE = 0.08                # where the flight starts in its turn

out = []


def line(p, q, w=1.0, color=BLACK, dash=None, arrows=False):
    extra = ' stroke-dasharray="%s"' % dash if dash else ""
    if arrows:
        extra += ' marker-start="url(#ar)" marker-end="url(#ar)"'
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.1f"%s/>'
               % (p[0], p[1], q[0], q[1], color, w, extra))


def poly(pts, w, color=BLACK):
    out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%.1f" stroke-linejoin="round"/>'
               % (" ".join("%.1f,%.1f" % q for q in pts), color, w))


def label(x, y, text):
    out.append('<text x="%.1f" y="%.1f" %s text-anchor="middle">%s</text>' % (x, y + 7, FONT, text))


def y_at(x, r, shift=0.0):
    return CY - r * math.sin(2 * math.pi * ((x - X0 + shift) / P + PHASE))


out.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">' % (W, H, W, H))
out.append('<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse"><path d="M0,1 L10,5 L0,9 z" fill="%s"/></marker></defs>' % BLACK)
out.append('<rect width="100%" height="100%" fill="white"/>')

# axis (blue dash-dot)
line((X0 - 10, CY), (X1 + 14, CY), 1.3, BLUE, AXIS_DASH)

# shaft (thick)
line((X0, CY - R_IN), (X1, CY - R_IN), 2.2)
line((X0, CY + R_IN), (X1, CY + R_IN), 2.2)

# flight: outer edge as two close curves (sheet thickness), inner edge on the shaft (thin)
xs = [X0 + (X1 - X0) * i / 300 for i in range(301)]
poly([(x, y_at(x, R_OUT)) for x in xs], 2.2)
poly([(x, y_at(x, R_OUT, -3.0)) for x in xs], 1.0)
poly([(x, y_at(x, R_IN)) for x in xs], 1.0)
# ends of the flight (radial lines at the screw ends)
for x in (X0, X1):
    line((x, y_at(x, R_IN)), (x, y_at(x, R_OUT)), 1.4)

# ---- P: between two troughs (lowest points of the outer edge)
troughs = []
k = 0
while True:
    # sin(...) = -1  ->  (x - X0)/P + PHASE = 0.75 + k
    x = X0 + (0.75 + k - PHASE) * P
    if x > X1:
        break
    if x >= X0:
        troughs.append(x)
    k += 1
y_ext = CY + R_OUT
y_p = y_ext + 32
if len(troughs) >= 2:
    a, b = troughs[0], troughs[1]
    for x in (a, b):
        line((x, y_ext + 3), (x, y_p + 6))
    line((a + 1.5, y_p), (b - 1.5, y_p), 1.4, arrows=True)
    label((a + b) / 2, y_p - 13, "P")

# ---- L: total screw length
y_l = y_p + 44
for x in (X0, X1):
    line((x, CY + R_IN + 6), (x, y_l + 6))
line((X0 + 1.5, y_l), (X1 - 1.5, y_l), 1.4, arrows=True)
label((X0 + X1) / 2, y_l - 13, "L")

# ---- ID and OD on the right
x_id, x_od = X1 + 34, X1 + 76
for y in (CY - R_IN, CY + R_IN):
    line((X1 + 4, y), (x_id + 6, y))
line((x_id, CY - R_IN + 1.5), (x_id, CY + R_IN - 1.5), 1.4, arrows=True)
label(x_id - 1, CY - R_IN - 18, "ID")
for y in (CY - R_OUT, CY + R_OUT):
    line((X1 - 30, y), (x_od + 6, y))
line((x_od, CY - R_OUT + 1.5), (x_od, CY + R_OUT - 1.5), 1.4, arrows=True)
label(x_od - 1, CY - R_OUT - 14, "OD")

out.append("</svg>")
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(root, "resources", "diagrams", "screw.svg")
os.makedirs(os.path.dirname(path), exist_ok=True)
open(path, "w").write("\n".join(out))
print("wrote", path)
