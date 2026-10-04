"""Generates resources/diagrams/transition_rect_round.svg
(task-panel parameter picture for the rectangular -> round eccentric transition).

Left:  top view - rectangle with its edges measured from the round's centre
       (A left, B right, E top, F bottom) and the round outlet D on the centre.
Right: side view - height H between the rectangular and the round end.
Same drawing style as the elbow diagram (make_elbow_diagram.py).
Run:  python tools/make_transition_diagram.py
"""
import math
import os

W, H = 334, 250
BLACK = "#111"
BLUE = "#2a56d6"           # axis colour, same blue as the elbow diagram
AXIS_DASH = "7,3,2,3"      # dash-dot
FONT = 'font-family="Arial" font-size="20" font-weight="bold" fill="%s"' % BLACK

# geometry in px (proportions of the reference sketch)
OX, OY = 136, 118           # round centre / origin of the A, B, E, F dimensions
A, B = 114, 72              # rectangle: left / right of the centre
E, F = 60, 94               # rectangle: above / below the centre
R = 86                      # round radius (D = 2R)

# side view (right)
SX_AXIS = 316               # vertical axis of the side view
SH = 112                    # drawn height H
S_TOP_X, S_BOT_X = 292, 274 # left ends of the round (top) and rectangle (bottom) lines
D_ANGLE = math.radians(38)  # direction of the D dimension line

s = []
s.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">' % (W, H, W, H))
s.append('<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
         'orient="auto-start-reverse"><path d="M0,1 L10,5 L0,9 z" fill="%s"/></marker></defs>' % BLACK)
s.append('<rect width="100%" height="100%" fill="white"/>')


def line(x1, y1, x2, y2, width=1.0, dash=None, arrows=False, color=BLACK):
    extra = ' stroke-dasharray="%s"' % dash if dash else ""
    if arrows:
        extra += ' marker-start="url(#ar)" marker-end="url(#ar)"'
    s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.1f"%s/>'
             % (x1, y1, x2, y2, color, width, extra))


def axis(x1, y1, x2, y2):
    line(x1, y1, x2, y2, 1.3, dash=AXIS_DASH, color=BLUE)


def label(x, y, text):
    s.append('<text x="%.1f" y="%.1f" %s text-anchor="middle">%s</text>' % (x, y, FONT, text))


left, right, top, bottom = OX - A, OX + B, OY - E, OY + F

# axes through the round centre (blue dash-dot)
axis(left - 12, OY, OX + R + 6, OY)
axis(OX, OY - R - 8, OX, bottom + 12)

# outlines: rectangle and round (thick)
s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="%s" stroke-width="2.2"/>'
         % (left, top, A + B, E + F, BLACK))
s.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-width="2.2"/>'
         % (OX, OY, R, BLACK))

# A and B: horizontal, below the axis
yd = OY + 32
line(left + 2, yd, OX - 2, yd, 1.4, arrows=True)
line(OX + 2, yd, right - 2, yd, 1.4, arrows=True)
label((left + OX) / 2, yd - 7, "A")
label((OX + right) / 2, yd - 7, "B")

# E and F: vertical, just left of the vertical axis
xe, xf = OX - 14, OX - 28
line(xe, top + 2, xe, OY - 2, 1.4, arrows=True)
line(xf, OY + 2, xf, bottom - 2, 1.4, arrows=True)
label(xe - 14, (top + OY) / 2 + 7, "E")
label(xf - 14, OY + F * 0.72 + 7, "F")

# D: diameter through the centre, arrows on the round
dx, dy = R * math.cos(D_ANGLE), R * math.sin(D_ANGLE)
line(OX - dx + 1.5, OY + dy - 1.2, OX + dx - 1.5, OY - dy + 1.2, 1.4, arrows=True)
label(OX - dx - 14, OY + dy + 16, "D")

# ---- side view: H
ty, by = OY - SH / 2, OY + SH / 2
axis(SX_AXIS, ty - 14, SX_AXIS, by + 14)
line(S_TOP_X, ty, SX_AXIS + 8, ty, 2.2)        # round end
line(S_BOT_X, by, SX_AXIS + 12, by, 2.2)       # rectangular end
line(S_TOP_X, ty, S_BOT_X, by, 2.2)            # sloping (eccentric) side
xh = 262
line(xh - 6, ty, S_TOP_X - 4, ty)              # extension lines
line(xh - 6, by, S_BOT_X - 4, by)
line(xh, ty + 2, xh, by - 2, 1.4, arrows=True)
label(xh - 15, OY + 7, "H")

s.append("</svg>")

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "resources", "diagrams", "transition_rect_round.svg")
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write("\n".join(s))
print("wrote", out)
