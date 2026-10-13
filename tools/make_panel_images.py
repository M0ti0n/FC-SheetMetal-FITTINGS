"""Renders an image of each tool's task panel for the README (docs/images/*_panel.png).

The panels are rebuilt in HTML in FreeCAD's task-panel style with the same
sections, fields and default values as the real panels, then captured with
Playwright / Chromium:

    python tools/make_panel_images.py
"""
import html
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
ICONS = ROOT / "resources" / "icons"
DIAGRAMS = ROOT / "resources" / "diagrams"

# ---------------------------------------------------------------- panel specs
# field: (label, value, kind) kind: "q" quantity, "spin" integer, "combo" editable list
# check: (label, checked, extra, indent) extra: None or value shown in a box next to it
TOOLS = [
    dict(key="elbow", title="Segmented elbow", icon="SegmentedElbow.svg", diagram="elbow.svg",
         fields=[("Diameter (D)", "400,00 mm", "q"), ("Elbow angle (A)", "90,00 °", "q"),
                 ("Centreline radius (R)", "800,00 mm", "q"), ("Number of middle sections (N)", "3", "spin")],
         pattern=[("Add folding lines", True, "24", 0), ("Add reference dimensions", False, None, 0),
                  ("Add folding labels", False, None, 0)],
         preview=[("Middle sec. (N)", True, None, 1), ("End sec. (B)", True, None, 1),
                  ("Add annotations", False, None, 0)]),
    dict(key="transition", title="Rectangular to round transition", icon="RectRoundTransition.svg",
         diagram="transition_rect_round.svg",
         fields=[("AB side (A)", "300,00 mm", "q"), ("AB side (B)", "200,00 mm", "q"),
                 ("EF side (E)", "150,00 mm", "q"), ("EF side (F)", "250,00 mm", "q"),
                 ("Diameter (D)", "400,00 mm", "q"), ("Height (H)", "300,00 mm", "q"),
                 ("Sections per quarter (N)", "4", "spin")],
         pattern=[("Add folding lines", True, "20", 0), ("Add reference dimensions", False, None, 0),
                  ("Add folding labels", False, None, 0)],
         preview=[("Combined", True, None, 1), ("Short Side", False, None, 1), ("Long Side", False, None, 1),
                  ("Add annotations", False, None, 0)]),
    dict(key="branch_reducer", title="Branch reducer", icon="BranchReducer.svg", diagram="reducer_branch.svg",
         fields=[("Top diameter (D1)", "200,00 mm", "q"), ("Bottom diameter (D2)", "400,00 mm", "q"),
                 ("Height (H1)", "400,00 mm", "q"), ("Branch height (H2)", "200,00 mm", "q"),
                 ("Branch diameter (D3)", "160,00 mm", "q"), ("Branch length (L)", "250,00 mm", "q"),
                 ("Branch angle (A)", "30,00 °", "q")],
         pattern=[("Add folding lines", True, "24", 0), ("Add reference dimensions", False, None, 0),
                  ("Add folding labels", False, None, 0)],
         preview=[("Reducer", True, None, 1), ("Branch", True, None, 1), ("Add annotations", False, None, 0)]),
    dict(key="flange", title="Flange", icon="Flange.svg", diagram="flange.svg",
         fields=[("Diameter (A)", "400", "combo"), ("Slot circle (B)", "435,00 mm", "q"),
                 ("Slot width (M)", "11,00 mm", "q"), ("Number of slots (N)", "10", "spin"),
                 ("Ring width (E)", "30,00 mm", "q"), ("Thickness (T)", "8,00 mm", "q")],
         info="D = 460 mm   (standard size)",
         pattern=[("Add reference dimensions", False, None, 0)],
         preview=[("Combined", True, None, 1), ("Divided", False, None, 1), ("Add annotations", False, None, 0)]),
    dict(key="thread_flange", title="Threaded flange", icon="ThreadFlange.svg", diagram="flange_cross.svg",
         fields=[("Diameter (A)", "400", "combo"), ("Hole circle (B)", "435,00 mm", "q"),
                 ("Thread (M)", "M8", "combo"), ("Number of holes (N)", "10", "spin"),
                 ("Ring width (E)", "30,00 mm", "q"), ("Thickness (T)", "10,00 mm", "q")],
         info="D = 460 mm, tap drill 6.8 mm  (standard size)",
         pattern=[("Add cross marks", True, "10,00 mm", 0), ("Add reference dimensions", False, None, 0)],
         preview=[("Combined", True, None, 1), ("Divided", False, None, 1), ("Add annotations", False, None, 0)]),
    dict(key="screw", title="Screw flight", icon="ScrewFlight.svg", diagram="screw.svg",
         fields=[("Outer diameter (OD)", "315,00 mm", "q"), ("Inner diameter (ID)", "101,60 mm", "q"),
                 ("Pitch (P)", "300,00 mm", "q"), ("Screw length (L)", "1000,00 mm", "q"),
                 ("Gap at inner edge", "6,00 mm", "q")],
         result=[("Blank inner radius", "78.42 mm"), ("Blank outer radius", "185.12 mm"),
                 ("Calculated angle", "320.06°"), ("Extension", "35.56°"),
                 ("<b>Blank angle</b>", "<b>355.61°</b>"), ("Gap inner / outer", "6 / 14.2 mm"),
                 ("<b>Pieces</b>", "<b>4</b>&nbsp; (L/P = 3.33)")],
         pattern=[("Add reference dimensions", False, None, 0)],
         preview=[("Add annotations", False, None, 0)]),
]

CSS = """
* { box-sizing: border-box; }
body { margin: 0; padding: 10px; background: #e9e9e9; font: 13px "Segoe UI", "DejaVu Sans", Arial, sans-serif;
       color: #1d1d1d; }
#panel { width: 340px; background: #f6f6f6; border: 1px solid #bdbdbd; }
.tasks { display: flex; justify-content: space-between; padding: 4px 8px; background: #fbfbfb;
         border-bottom: 1px solid #d0d0d0; color: #333; }
.okc { display: flex; gap: 8px; justify-content: center; padding: 8px; }
.btn { border: 1px solid #a9a9a9; border-radius: 3px; background: linear-gradient(#fdfdfd, #e7e7e7);
       padding: 4px 0; width: 104px; text-align: center; }
.btn.ok { border-color: #5b8fd6; background: linear-gradient(#e9f2fd, #cfe2fa); }
.box { margin: 6px 6px 8px; background: #fff; border: 1px solid #c9c9c9; }
.hdr { display: flex; align-items: center; gap: 6px; padding: 5px 8px; font-weight: 600;
       background: linear-gradient(#f3f6fa, #e3e9f1); border-bottom: 1px solid #c9cfd8; }
.hdr img { width: 18px; height: 18px; }
.hdr .arr { margin-left: auto; font-size: 10px; color: #444; }
.title { font-size: 14px; }
.body { padding: 8px 10px; }
.diagram { text-align: center; padding: 2px 0 8px; }
.diagram img { width: 290px; }
.row { display: flex; align-items: center; justify-content: space-between; margin: 4px 0; gap: 6px; }
.row label { flex: 1; }
.q { width: 132px; height: 24px; border: 1px solid #b4b4b4; background: #fff; display: flex;
     align-items: center; padding: 0 3px 0 6px; justify-content: space-between; }
.q .fx { font-size: 9px; color: #fff; background: #3c78c8; border-radius: 2px; padding: 1px 2px;
         font-style: italic; font-weight: bold; }
.q .spin { font-size: 7px; line-height: 7px; color: #555; margin-left: 3px; }
.q .v { flex: 1; text-align: right; padding-right: 4px; white-space: nowrap; }
.q .dd { font-size: 9px; color: #555; }
.check { display: flex; align-items: center; gap: 6px; margin: 5px 0; }
.check.ind { margin-left: 22px; }
.cb { width: 14px; height: 14px; border: 1px solid #7a7a7a; background: #fff; display: inline-flex;
      align-items: center; justify-content: center; font-size: 11px; line-height: 1; color: #fff; }
.cb.on { background: #3c78c8; border-color: #2f62a5; }
.grid { display: flex; align-items: center; justify-content: space-between; }
.blue { background: linear-gradient(#3f86e6, #2e6fcf); color: #fff; border: 1px solid #2a5fb0;
        border-radius: 3px; padding: 5px 0; width: 130px; text-align: center; }
.info { color: #7a7a7a; margin: 6px 0 2px; text-align: right; font-size: 12px; }
.result { border: 1px solid #c9c9c9; background: #fff; padding: 6px 8px; margin-top: 8px; }
.result td { padding: 1px 0; } .result td.r { text-align: right; padding-left: 14px; }
.small { width: 112px; }
"""


def q_widget(value, kind, small=False):
    v = html.escape(value)
    cls = "q small" if small else "q"
    if kind == "combo":
        return '<div class="%s"><span class="v">%s</span><span class="dd">▼</span></div>' % (cls, v)
    if kind == "spin":
        return '<div class="%s"><span class="v">%s</span><span class="spin">▲<br>▼</span></div>' % (cls, v)
    if kind == "ro":
        return '<div class="%s" style="background:#f1f1f1"><span class="v">%s</span></div>' % (cls, v)
    return ('<div class="%s"><span class="v">%s</span><span class="fx">fx</span>'
            '<span class="spin">▲<br>▼</span></div>' % (cls, v))


def check(label, on, extra=None, indent=0, extra_kind="spin"):
    box = '<span class="cb on">✔</span>' if on else '<span class="cb"></span>'
    left = '<div class="check%s">%s<span>%s</span></div>' % (" ind" if indent else "", box, html.escape(label))
    if extra is None:
        return left
    return '<div class="grid">%s%s</div>' % (left, q_widget(extra, extra_kind, small=True))


def section(title, body, icon=None, big=False):
    ic = '<img src="%s">' % (ICONS / icon).as_uri() if icon else ""
    return ('<div class="box"><div class="hdr">%s<span class="%s">%s</span><span class="arr">▲</span></div>'
            '<div class="body">%s</div></div>' % (ic, "title" if big else "", html.escape(title), body))


def panel_html(t):
    main = '<div class="diagram"><img src="%s"></div>' % (DIAGRAMS / t["diagram"]).as_uri()
    for label, value, kind in t["fields"]:
        main += '<div class="row"><label>%s</label>%s</div>' % (html.escape(label), q_widget(value, kind))
    if t.get("info"):
        main += '<div class="info">%s</div>' % html.escape(t["info"])
    if t.get("result"):
        main += '<div class="result"><table cellspacing="0">%s</table></div>' % "".join(
            '<tr><td>%s</td><td class="r">%s</td></tr>' % row for row in t["result"])
    pat = ""
    for label, on, extra, ind in t["pattern"]:
        kind = "ro" if (t["key"] == "transition" and extra) else ("q" if extra and "mm" in extra else "spin")
        pat += check(label, on, extra, ind, kind)
    prev = '<div class="grid">%s<div class="blue">Generate</div></div>' % check("Show flat pattern", True)
    for label, on, extra, ind in t["preview"]:
        prev += check(label, on, extra, ind)
    exp = '<div class="grid"><span></span><div class="blue">Export DXF</div></div>'
    return ("<!doctype html><html><head><meta charset='utf-8'><style>%s</style></head><body>"
            "<div id='panel'><div class='tasks'><span>Tasks</span><span>□ ⧉</span></div>"
            "<div class='okc'><div class='btn ok'>OK</div><div class='btn'>Cancel</div></div>"
            "%s%s%s%s</div></body></html>" % (
                CSS,
                section(t["title"], main, t["icon"], big=True).replace(
                    '<div class="body">', '<div class="hdr" style="background:#eef2f7">Main Parameters'
                    '<span class="arr">▲</span></div><div class="body">', 1),
                section("Flat Pattern Options", pat), section("Preview Options", prev),
                section("Export Options", exp)))


def main():
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "_panel.html"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(device_scale_factor=2, viewport={"width": 380, "height": 1400})
        for t in TOOLS:
            tmp.write_text(panel_html(t), encoding="utf-8")
            page.goto(tmp.as_uri())
            page.wait_for_timeout(150)
            page.locator("#panel").screenshot(path=str(OUT / ("%s_panel.png" % t["key"])))
            print("wrote", OUT / ("%s_panel.png" % t["key"]))
        browser.close()
    tmp.unlink()


if __name__ == "__main__":
    main()
