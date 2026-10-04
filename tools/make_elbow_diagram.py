"""Generates resources/diagrams/elbow.svg (the task-panel parameter picture).

Drawn from real segmented-elbow geometry (90 deg, N = 3) so the picture is
always consistent with the convention: 1/2 + N + 1/2.
Run:  python tools/make_elbow_diagram.py
"""
import math
import os

W, H = 320, 270
CX, CY = 238, 222         # bend centre (bottom right, on the baseline)
R, r = 150, 46            # centreline radius / half diameter in px
N = 3
A = 90.0
theta = math.radians(A / (N + 1))

BLACK, BLUE, RED = "#111", "#2a56d6", "#d22"


def pt(rad, ang):
    """Polar around the centre; ang in radians measured from +x, y up."""
    return CX + rad * math.cos(ang), CY - rad * math.sin(ang)


def P(p):
    return "%.1f,%.1f" % p


# joint angles, from the vertical start leg (180 deg) to the top (90 deg)
a_start, a_end = math.pi, math.pi / 2
joints = [a_start - theta / 2 - k * theta for k in range(N + 1)]
k_out = (R + r) / math.cos(theta / 2)
k_in = (R - r) / math.cos(theta / 2)

outer = [pt(R + r, a_start)] + [pt(k_out, a) for a in joints] + [pt(R + r, a_end)]
inner = [pt(R - r, a_start)] + [pt(k_in, a) for a in joints] + [pt(R - r, a_end)]

s = []
s.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">' % (W, H, W, H))
s.append('<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
         'orient="auto-start-reverse"><path d="M0,1 L10,5 L0,9 z" fill="%s"/></marker></defs>' % BLACK)
s.append('<rect width="100%" height="100%" fill="white"/>')

# baseline + vertical axis through the centre (dash-dot)
s.append('<line x1="18" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1" stroke-dasharray="7,3,2,3"/>'
         % (CY, W - 6, CY, BLACK))
s.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1" stroke-dasharray="7,3,2,3"/>'
         % (CX, 28, CX, H - 10, BLACK))

# centreline (red dash-dot), polyline through the section mid points
cl = [pt(R, a_start)] + [pt(R / math.cos(theta / 2), a) for a in joints] + [pt(R, a_end)]
s.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.4" stroke-dasharray="9,3,2,3"/>'
         % (" ".join(P(p) for p in cl), RED))
# straight extension of the centreline below the start face (like the mockup)
x0 = pt(R, a_start)[0]
s.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1.4" stroke-dasharray="9,3,2,3"/>'
         % (x0, CY, x0, CY + 14, RED))

# joints (blue dashed)
for a in joints:
    s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.6" stroke-dasharray="6,4"/>'
             % (*pt(k_in, a), *pt(k_out, a), BLUE))

# outline
poly = outer + list(reversed(inner))
s.append('<polygon points="%s" fill="none" stroke="%s" stroke-width="2.2" stroke-linejoin="round"/>'
         % (" ".join(P(p) for p in poly), BLACK))

# ---- D: vertical dimension at the end face (top right)
ex = pt(R + r, a_end)[0] + 26
y_top, y_bot = pt(R + r, a_end)[1], pt(R - r, a_end)[1]
for y in (y_top, y_bot):
    s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>' % (CX + 4, y, ex + 6, y, BLACK))
s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.4" '
         'marker-start="url(#ar)" marker-end="url(#ar)"/>' % (ex, y_top + 2, ex, y_bot - 2, BLACK))
s.append('<text x="%.1f" y="%.1f" font-family="Arial" font-size="20" font-weight="bold">D</text>'
         % (ex + 8, (y_top + y_bot) / 2 + 7))

# ---- B: end section label on the bottom (start) end section, leader from the left
b_y = (CY + pt(k_out, joints[0])[1]) / 2 + 4          # half way up the end section
b_x_out = pt(R + r, a_start)[0]                         # outer edge of the end section
s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.4"/>'
         % (b_x_out - 16, b_y, b_x_out + 22, b_y, BLACK))
s.append('<text x="%.1f" y="%.1f" font-family="Arial" font-size="20" font-weight="bold">B</text>'
         % (b_x_out - 32, b_y + 7))

# ---- N: label top-left, arrows into each middle section
nx, ny = 34, 50
s.append('<text x="%d" y="%d" font-family="Arial" font-size="20" font-weight="bold">N</text>' % (nx, ny))
for k in range(N):
    am = (joints[k] + joints[k + 1]) / 2
    tx, ty = pt(R + r * 0.25, am)
    s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.3" marker-end="url(#ar)"/>'
             % (nx + 14, ny + 6, tx, ty, BLACK))

# ---- R: from the start centreline to the bend centre, above the baseline
ry = CY - 14
s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.4" '
         'marker-start="url(#ar)" marker-end="url(#ar)"/>' % (x0 + 2, ry, CX - 2, ry, BLACK))
s.append('<text x="%.1f" y="%.1f" font-family="Arial" font-size="20" font-weight="bold">R</text>'
         % ((x0 + CX) / 2 - 6, ry - 8))

# ---- A: angle arc at the centre between baseline (left) and vertical
ra = 46
p1, p2 = pt(ra, math.pi * 0.98), pt(ra, math.pi / 2 * 1.04)
s.append('<path d="M%.1f,%.1f A%d,%d 0 0 1 %.1f,%.1f" fill="none" stroke="%s" stroke-width="1.4" '
         'marker-start="url(#ar)" marker-end="url(#ar)"/>' % (*p1, ra, ra, *p2, BLACK))
s.append('<text x="%.1f" y="%.1f" font-family="Arial" font-size="20" font-weight="bold">A</text>'
         % (CX - ra - 4, CY - ra - 8))

s.append("</svg>")

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "resources", "diagrams", "elbow.svg")
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write("\n".join(s))
print("wrote", out)
