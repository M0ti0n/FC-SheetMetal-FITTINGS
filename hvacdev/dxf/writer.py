# SPDX-License-Identifier: LGPL-2.1-or-later
"""Minimal dependency-free DXF R12 (AC1009) writer.

R12 is deliberately chosen: every CAM / nesting package reads it.
Layers:
    CUT    - cutting contour (closed polyline)
    FOLD   - press-brake fold marks (short solid lines at both edges)
    REF    - centre / reference lines (centre linetype)
    TEXT   - labels
    DIM    - reference dimensions (drawn as lines + text, no DIMENSION entity)
"""

LAYERS = {
    # name: (ACI colour, linetype)
    "CUT": (7, "CONTINUOUS"),
    "FOLD": (1, "CONTINUOUS"),   # short solid fold marks
    "REF": (3, "CENTER"),
    "TEXT": (2, "CONTINUOUS"),
    "DIM": (4, "CONTINUOUS"),
}

LINETYPES = {
    "CONTINUOUS": ("Solid line", []),
    "DASHED": ("Dashed __ __ __", [12.0, -6.0]),
    "CENTER": ("Center ____ _ ____", [30.0, -6.0, 6.0, -6.0]),
}


class DxfWriter:
    def __init__(self):
        self._entities = []

    # ------------------------------------------------------------ entities
    def line(self, p1, p2, layer):
        self._entities.append(
            "0\nLINE\n8\n%s\n10\n%.4f\n20\n%.4f\n30\n0.0\n11\n%.4f\n21\n%.4f\n31\n0.0\n"
            % (layer, p1[0], p1[1], p2[0], p2[1]))

    def polyline(self, points, layer, closed=False, bulges=None):
        """POLYLINE of lines and arcs. bulges[i] is the arc of the segment that
        starts at points[i] (0 = straight, tan(sweep/4) otherwise). No splines."""
        pts = list(points)
        bl = list(bulges) if bulges else [0.0] * len(pts)
        if closed and len(pts) > 1 and _same(pts[0], pts[-1]):
            pts, bl = pts[:-1], bl[:-1] if len(bl) == len(pts) else bl
        out = ["0\nPOLYLINE\n8\n%s\n66\n1\n10\n0.0\n20\n0.0\n30\n0.0\n70\n%d\n"
               % (layer, 1 if closed else 0)]
        for i, (x, y) in enumerate(pts):
            out.append("0\nVERTEX\n8\n%s\n10\n%.4f\n20\n%.4f\n30\n0.0\n" % (layer, x, y))
            b = bl[i] if i < len(bl) else 0.0
            if abs(b) > 1e-12:
                out.append("42\n%.10f\n" % b)
        out.append("0\nSEQEND\n8\n%s\n" % layer)
        self._entities.append("".join(out))

    def contour(self, segs, layer, closed=True):
        """Chain of arcs.Seg objects (lines / arcs) as one polyline."""
        self.polyline([sg.start for sg in segs] + ([] if closed else [segs[-1].end]), layer,
                      closed=closed, bulges=[sg.bulge() for sg in segs] + ([] if closed else [0.0]))

    def text(self, pos, value, height, layer="TEXT", rotation=0.0, center=False):
        value = str(value).replace("\n", " ")
        if center:
            # horizontal centre (72=1) + middle (73=2); needs the 11/21 point
            self._entities.append(
                "0\nTEXT\n8\n%s\n10\n%.4f\n20\n%.4f\n30\n0.0\n40\n%.4f\n1\n%s\n50\n%.4f\n"
                "72\n1\n11\n%.4f\n21\n%.4f\n31\n0.0\n73\n2\n"
                % (layer, pos[0], pos[1], height, value, rotation, pos[0], pos[1]))
        else:
            self._entities.append(
                "0\nTEXT\n8\n%s\n10\n%.4f\n20\n%.4f\n30\n0.0\n40\n%.4f\n1\n%s\n50\n%.4f\n"
                % (layer, pos[0], pos[1], height, value, rotation))

    # ------------------------------------------------------------ output
    def tostring(self):
        parts = ["0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1009\n9\n$INSUNITS\n70\n4\n0\nENDSEC\n"]
        parts.append("0\nSECTION\n2\nTABLES\n")
        parts.append("0\nTABLE\n2\nLTYPE\n70\n%d\n" % len(LINETYPES))
        for name, (desc, pattern) in LINETYPES.items():
            parts.append("0\nLTYPE\n2\n%s\n70\n0\n3\n%s\n72\n65\n73\n%d\n40\n%.4f\n"
                         % (name, desc, len(pattern), sum(abs(v) for v in pattern)))
            for v in pattern:
                parts.append("49\n%.4f\n" % v)
        parts.append("0\nENDTAB\n")
        parts.append("0\nTABLE\n2\nLAYER\n70\n%d\n" % len(LAYERS))
        for name, (colour, ltype) in LAYERS.items():
            parts.append("0\nLAYER\n2\n%s\n70\n0\n62\n%d\n6\n%s\n" % (name, colour, ltype))
        parts.append("0\nENDTAB\n0\nENDSEC\n")
        parts.append("0\nSECTION\n2\nENTITIES\n")
        parts.extend(self._entities)
        parts.append("0\nENDSEC\n0\nEOF\n")
        return "".join(parts)

    def save(self, path):
        with open(path, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
            f.write(self.tostring())


def _same(a, b, tol=1e-9):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol
