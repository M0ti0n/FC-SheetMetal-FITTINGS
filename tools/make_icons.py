"""Toolbar icons (Tango / FreeCAD palette), written as SVG + PNG from the same shapes.

    python tools/make_icons.py

Outputs
    resources/icons/SegmentedElbow.svg, RectRoundTransition.svg   (toolbar, default colour)
    resources/icons/png/<name>_<colour>_<size>.png                 (64 and 256 px)
    resources/icons/variants/<name>_<colour>.svg                   (other colour options)

Elbow: flat 2D elbow, every section shaded like a lit cylinder, dark joint lines.
Transition: small 3D model of the real fitting (rectangle below, round on top),
facets lit from the upper left, inside visible through the round opening.
"""
import math
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "resources", "icons")

# Tango palette as used by FreeCAD icons: (light, mid, dark, outline)
PALETTES = {
    "blue":   ("#9cc3ec", "#3465a4", "#1d3f6e", "#0b1521"),
    "orange": ("#fcd28a", "#f57900", "#a74300", "#2e1a05"),
    "green":  ("#c4f08a", "#73d216", "#3f7a06", "#14240a"),
    "metal":  ("#f2f3f1", "#a6aaa3", "#5d605a", "#1f2223"),
}
DEFAULT = "blue"


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in c)


def lerp(c1, c2, t):
    a, b = hex2rgb(c1), hex2rgb(c2)
    return rgb2hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def shade(pal, s):
    """s in 0..1: 0 = darkest, 0.5 = mid, 1 = lightest."""
    light, mid, dark, _ = pal
    return lerp(dark, mid, s * 2) if s < 0.5 else lerp(mid, light, (s - 0.5) * 2)


class Icon:
    """Shapes in a 64 x 64 coordinate system."""

    def __init__(self):
        self.items = []          # ("poly", pts, fill, stroke, width) / ("line", pts, None, stroke, width)

    def poly(self, pts, fill, stroke=None, width=0.0):
        self.items.append(("poly", pts, fill, stroke, width))

    def line(self, pts, stroke, width, closed=False):
        if closed:
            pts = list(pts) + [pts[0]]
        self.items.append(("line", pts, None, stroke, width))

    def svg(self):
        out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">']
        for kind, pts, fill, stroke, width in self.items:
            p = " ".join("%.2f,%.2f" % q for q in pts)
            if kind == "poly":
                # stroke in the fill colour closes hairline gaps between facets
                st = stroke or fill
                sw = width if stroke else 0.35
                out.append('<polygon points="%s" fill="%s" stroke="%s" stroke-width="%.2f" '
                           'stroke-linejoin="round"/>' % (p, fill, st, sw))
            else:
                out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%.2f" '
                           'stroke-linejoin="round" stroke-linecap="round"/>' % (p, stroke, width))
        out.append("</svg>")
        return "\n".join(out)

    def png(self, size):
        ss = 4                                   # supersampling
        S = size * ss / 64.0
        img = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for kind, pts, fill, stroke, width in self.items:
            q = [(x * S, y * S) for x, y in pts]
            if kind == "poly":
                d.polygon(q, fill=hex2rgb(fill) + (255,))
                d.line(q + [q[0]], fill=hex2rgb(stroke or fill) + (255,),
                       width=max(1, int(round((width if stroke else 0.35) * S))), joint="curve")
            else:
                w = max(1, int(round(width * S)))
                d.line(q, fill=hex2rgb(stroke) + (255,), width=w, joint="curve")
                r = w / 2.0                       # round caps
                for x, y in (q[0], q[-1]):
                    d.ellipse((x - r, y - r, x + r, y + r), fill=hex2rgb(stroke) + (255,))
        return img.resize((size, size), Image.LANCZOS)


# --------------------------------------------------------------------- elbow
def elbow_icon(pal):
    ic = Icon()
    cx, cy, R, r, N = 58.0, 60.0, 37.0, 13.5, 2
    t = math.radians(90.0 / (N + 1))
    joints = [math.pi - t / 2 - k * t for k in range(N + 1)]

    def pt(d, a):
        return (cx + d * math.cos(a), cy - d * math.sin(a))

    ko, ki = (R + r) / math.cos(t / 2), (R - r) / math.cos(t / 2)
    outer = [pt(R + r, math.pi)] + [pt(ko, a) for a in joints] + [pt(R + r, math.pi / 2)]
    inner = [pt(R - r, math.pi)] + [pt(ki, a) for a in joints] + [pt(R - r, math.pi / 2)]

    strips = 32
    for i in range(len(outer) - 1):              # each section, shaded like a cylinder
        for k in range(strips):
            u0, u1 = k / strips, (k + 1) / strips
            # u = 0 inner (throat) .. 1 outer (heel); light falls from the upper left
            uc = (u0 + u1) / 2
            s = 0.18 + 0.82 * max(0.0, math.cos((uc - 0.68) * math.pi * 0.95))

            def mix(a, b, u):
                return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)

            q = [mix(inner[i], outer[i], u0), mix(inner[i], outer[i], u1),
                 mix(inner[i + 1], outer[i + 1], u1), mix(inner[i + 1], outer[i + 1], u0)]
            ic.poly(q, shade(pal, s))
    outline = pal[3]
    for a in joints:                              # joints between sections
        ic.line([pt(ki, a), pt(ko, a)], outline, 1.6)
    ic.line(outer + list(reversed(inner)), outline, 2.4, closed=True)
    return ic


# ---------------------------------------------------------------- transition
def transition_icon(pal):
    """Isometric-style view of a rect -> round transition (eccentric)."""
    A, B, E, F = 1.05, 0.75, 0.55, 0.85            # rectangle around the round centre
    r, H, n = 0.62, 1.15, 6                        # round radius, height, sections/quarter
    corners = [(B, E, 0), (-A, E, 0), (-A, -F, 0), (B, -F, 0)]   # after sides at 0/90/180/270 deg

    def rnd(th):
        return (r * math.cos(th), r * math.sin(th), H)

    tris = []                                       # 3D triangles
    for j in range(4):
        c = corners[j]
        for k in range(n):
            a0 = j * math.pi / 2 + k * (math.pi / 2) / n
            a1 = j * math.pi / 2 + (k + 1) * (math.pi / 2) / n
            tris.append((c, rnd(a0), rnd(a1)))
        nxt = corners[(j + 1) % 4]
        tris.append((c, nxt, rnd((j + 1) * math.pi / 2)))      # flat side triangle

    az, el = math.radians(-32), math.radians(28)

    def view(p):
        x, y, z = p
        xr = x * math.cos(az) - y * math.sin(az)
        yr = x * math.sin(az) + y * math.cos(az)
        return (xr, z * math.cos(el) + yr * math.sin(el)), yr * math.cos(el) - z * math.sin(el)

    vdir = (-math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))  # towards camera
    light = (-0.55, -0.45, 0.70)
    ln = math.sqrt(sum(v * v for v in light))
    light = tuple(v / ln for v in light)

    def sub(a, b):
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    faces = []
    for t in tris:
        nrm = cross(sub(t[1], t[0]), sub(t[2], t[0]))
        L = math.sqrt(dot(nrm, nrm)) or 1.0
        nrm = tuple(v / L for v in nrm)
        cen = tuple(sum(p[i] for p in t) / 3 for i in range(3))
        if dot(nrm, (cen[0], cen[1], 0.0)) < 0:              # make it point outwards
            nrm = tuple(-v for v in nrm)
        front = dot(nrm, vdir) > 0
        lit = max(0.0, dot(nrm, light)) if front else max(0.0, dot(tuple(-v for v in nrm), light))
        s = (0.22 + 0.78 * lit) if front else (0.05 + 0.25 * lit)   # inside is darker
        pts2 = [view(p)[0] for p in t]
        depth = sum(view(p)[1] for p in t) / 3
        faces.append((depth, pts2, shade(pal, s), front))

    # fit into the 64 px box (y up -> screen down)
    xs = [p[0] for f in faces for p in f[1]]
    ys = [p[1] for f in faces for p in f[1]]
    sc = min(56.0 / (max(xs) - min(xs)), 56.0 / (max(ys) - min(ys)))
    ox = 32 - sc * (max(xs) + min(xs)) / 2
    oy = 32 + sc * (max(ys) + min(ys)) / 2

    def S(p):
        return (ox + sc * p[0], oy - sc * p[1])

    ic = Icon()
    outline = pal[3]
    # back faces first (inside), then front faces far -> near
    for depth, pts2, col, front in sorted(faces, key=lambda f: (f[3], -f[0])):
        ic.poly([S(p) for p in pts2], col)
    # outlines: round opening, visible rectangle edges, silhouette
    ring = [S(view(rnd(2 * math.pi * k / 72))[0]) for k in range(72)]
    ic.line(ring, outline, 2.0, closed=True)
    rect2 = [S(view(c)[0]) for c in corners]
    # rectangle edges: the two at the back are hidden by the body -> skip the farthest corner's edges
    far = max(range(4), key=lambda i: view(corners[i])[1])
    for i in range(4):
        a, b = i, (i + 1) % 4
        if far in (a, b):
            continue
        ic.line([rect2[a], rect2[b]], outline, 2.2)
    # silhouette: tangent lines from the left- and right-most corner to the round
    left_c = min(range(4), key=lambda i: rect2[i][0])
    right_c = max(range(4), key=lambda i: rect2[i][0])
    for ci, pick in ((left_c, min), (right_c, max)):
        cs = rect2[ci]
        cand = [S(view(rnd(2 * math.pi * k / 144))[0]) for k in range(144)]
        # silhouette generator = round point with the extreme screen x after projecting along the line
        q = pick(cand, key=lambda p: math.atan2(p[0] - cs[0], cs[1] - p[1]))
        ic.line([cs, q], outline, 2.0)
    return ic


def write(name, ic, colour, svg_path=None):
    os.makedirs(os.path.join(ICONS, "png"), exist_ok=True)
    os.makedirs(os.path.join(ICONS, "variants"), exist_ok=True)
    if svg_path:
        open(svg_path, "w").write(ic.svg())
    open(os.path.join(ICONS, "variants", "%s_%s.svg" % (name, colour)), "w").write(ic.svg())
    for size in (64, 256):
        ic.png(size).save(os.path.join(ICONS, "png", "%s_%s_%d.png" % (name, colour, size)))


if __name__ == "__main__":
    for colour, pal in PALETTES.items():
        default = colour == DEFAULT
        write("SegmentedElbow", elbow_icon(pal), colour,
              os.path.join(ICONS, "SegmentedElbow.svg") if default else None)
        write("RectRoundTransition", transition_icon(pal), colour,
              os.path.join(ICONS, "RectRoundTransition.svg") if default else None)
    print("icons written to", ICONS)
