# SPDX-License-Identifier: LGPL-2.1-or-later
"""Task panel for the screw flight (same layout as the other tools).

    Main Parameters        diagram + OD, ID, P, L, gap + live result
    Flat Pattern Options   add reference dimensions
    Preview Options        show flat pattern + Generate, add annotations
    Export Options         Export DXF
"""

import os
import re

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from hvacdev.geometry import screw as sg
from hvacdev.freecad import resources
from hvacdev.freecad import screw_feature as sf
from hvacdev.freecad.elbow_taskpanel import _diagram_pixmap, _quantity, _raw, DIAGRAM_WIDTH


class ScrewTaskPanel:
    def __init__(self, obj, is_new):
        self.obj = obj
        self.is_new = is_new
        self.doc = obj.Document
        if not is_new:
            self.doc.openTransaction("Edit screw flight")
        self.form = [self._main_box(), self._pattern_box(), self._preview_box(), self._export_box()]
        self._update_result()

    # ------------------------------------------------------------------ UI
    def _main_box(self):
        o = self.obj
        w = QtGui.QWidget()
        w.setWindowTitle("Main Parameters")
        w.setWindowIcon(QtGui.QIcon(resources.icon("ScrewFlight.svg")))
        lay = QtGui.QVBoxLayout(w)

        pic = QtGui.QLabel()
        pic.setAlignment(QtCore.Qt.AlignCenter)
        pic.setPixmap(_diagram_pixmap(resources.diagram("screw.svg"), DIAGRAM_WIDTH))
        pic.setToolTip("OD - outer diameter of the flight\nID - inner diameter of the flight (shaft)\n"
                       "P - pitch\nL - screw length (number of pieces = L / P)")
        lay.addWidget(pic)

        form = QtGui.QFormLayout()
        self.od = _quantity("mm", o.OuterDiameter.Value, 1.0)
        self.id = _quantity("mm", o.InnerDiameter.Value, 1.0)
        self.p = _quantity("mm", o.Pitch.Value, 1.0)
        self.ln = _quantity("mm", o.ScrewLength.Value, 1.0)
        self.gap = _quantity("mm", o.Gap.Value, 0.0, 1000.0)
        self.gap.setToolTip("The blank is extended until the two cut ends are this far apart\n"
                            "at the inner edge (the closest point)")
        form.addRow("Outer diameter (OD)", self.od)
        form.addRow("Inner diameter (ID)", self.id)
        form.addRow("Pitch (P)", self.p)
        form.addRow("Screw length (L)", self.ln)
        form.addRow("Gap at inner edge", self.gap)
        lay.addLayout(form)

        self.result = QtGui.QLabel()
        self.result.setTextFormat(QtCore.Qt.RichText)
        self.result.setStyleSheet("QLabel { background: palette(base); border: 1px solid palette(mid); "
                                  "padding: 6px; }")
        lay.addWidget(self.result)

        self._bindings = []
        for widget, prop in ((self.od, "OuterDiameter"), (self.id, "InnerDiameter"), (self.p, "Pitch"),
                             (self.ln, "ScrewLength"), (self.gap, "Gap")):
            widget.valueChanged.connect(self._update_result)
            try:
                b = Gui.ExpressionBinding(widget)
                b.bind(o, prop)
                self._bindings.append(b)
            except Exception:
                pass
        return w

    def _pattern_box(self):
        w = QtGui.QWidget()
        w.setWindowTitle("Flat Pattern Options")
        g = QtGui.QGridLayout(w)
        self.cb_dims = QtGui.QCheckBox("Add reference dimensions")
        self.cb_dims.setChecked(self.obj.AddReferenceDimensions)
        self.cb_dims.setToolTip("Blank radii, angles and gaps")
        g.addWidget(self.cb_dims, 0, 0)
        return w

    def _preview_box(self):
        o = self.obj
        w = QtGui.QWidget()
        w.setWindowTitle("Preview Options")
        g = QtGui.QGridLayout(w)
        self.cb_show = QtGui.QCheckBox("Show flat pattern")
        self.cb_show.setChecked(o.ShowFlatPattern)
        self.cb_anno = QtGui.QCheckBox("Add annotations")
        self.cb_anno.setChecked(o.AddAnnotations)
        self.cb_anno.setToolTip("Centre lines, end of the calculated part (start of the extension)\n"
                                "and piece label with the number of pieces")
        gen = QtGui.QPushButton("Generate")
        gen.setDefault(False)
        gen.setAutoDefault(False)
        g.addWidget(self.cb_show, 0, 0)
        g.addWidget(gen, 0, 1)
        g.addWidget(self.cb_anno, 1, 0)
        g.setContentsMargins(9, 9, 9, 9)
        g.setColumnStretch(0, 1)
        gen.clicked.connect(self.generate)
        self.cb_show.toggled.connect(self._visibility_changed)
        self.cb_anno.toggled.connect(self._options_changed)
        self.cb_dims.toggled.connect(self._options_changed)
        return w

    def _export_box(self):
        w = QtGui.QWidget()
        w.setWindowTitle("Export Options")
        lay = QtGui.QHBoxLayout(w)
        btn = QtGui.QPushButton("Export DXF")
        btn.setAutoDefault(False)
        btn.setToolTip("Exports exactly what is visible in the model space")
        lay.addStretch(1)
        lay.addWidget(btn)
        btn.clicked.connect(self.export_dxf)
        return w

    # ------------------------------------------------------------- helpers
    def _params(self):
        return sg.ScrewParams(od=_raw(self.od), id=_raw(self.id), pitch=_raw(self.p),
                              length=_raw(self.ln), gap=_raw(self.gap))

    def _update_result(self, *_):
        try:
            r = sg.calculate(self._params())
        except ValueError as exc:
            self.result.setText("<span style='color:#c00'>%s</span>" % str(exc).replace("\n", "<br>"))
            return
        rows = [("Blank inner radius", "%.2f mm" % r.ri),
                ("Blank outer radius", "%.2f mm" % r.ro),
                ("Calculated angle", "%.2f°" % r.calc_angle),
                ("Extension", "%.2f°" % r.extension),
                ("<b>Blank angle</b>", "<b>%.2f°</b>" % r.blank_angle),
                ("Gap inner / outer", "%g / %.1f mm" % (self._params().gap, r.gap_outer)),
                ("<b>Pieces</b>", "<b>%d</b>  (L/P = %.2f)" % (r.pieces, r.turns))]
        html = "<table cellspacing='0' cellpadding='1'>" + "".join(
            "<tr><td>%s</td><td align='right'>&nbsp;&nbsp;%s</td></tr>" % row for row in rows) + "</table>"
        if r.warnings:
            html += "<br><span style='color:#c60'>%s</span>" % " ".join(r.warnings)
        self.result.setText(html)

    # ------------------------------------------------------------- actions
    def _apply(self):
        p = self._params()
        try:
            sg.calculate(p)
        except ValueError as exc:
            QtGui.QMessageBox.warning(None, "Screw flight", str(exc))
            return False
        o = self.obj
        o.OuterDiameter = p.od
        o.InnerDiameter = p.id
        o.Pitch = p.pitch
        o.ScrewLength = p.length
        o.Gap = p.gap
        o.AddReferenceDimensions = self.cb_dims.isChecked()
        o.ShowFlatPattern = self.cb_show.isChecked()
        o.AddAnnotations = self.cb_anno.isChecked()
        if o.Label.startswith("Screw flight"):     # keep a name the user typed
            sf.update_label(o)
        return True

    def generate(self):
        if self._apply():
            self.obj.touch()
            self.doc.recompute()
            Gui.SendMsgToActiveView("ViewFit")

    def _visibility_changed(self, *_):
        self.obj.ShowFlatPattern = self.cb_show.isChecked()

    def _options_changed(self, *_):
        self.obj.AddAnnotations = self.cb_anno.isChecked()
        self.obj.AddReferenceDimensions = self.cb_dims.isChecked()
        self.obj.touch()
        self.doc.recompute()

    def export_dxf(self):
        self.generate()
        from hvacdev.freecad import export
        base = os.path.dirname(self.doc.FileName) if self.doc.FileName else os.path.expanduser("~")
        name = re.sub(r"[^\w.-]+", "_", self.obj.Label).strip("_") + ".dxf"
        res = QtGui.QFileDialog.getSaveFileName(None, "Export flat pattern DXF",
                                                os.path.join(base, name), "DXF (*.dxf)")
        path = res[0] if isinstance(res, tuple) else res
        if not path:
            return
        if not path.lower().endswith(".dxf"):
            path += ".dxf"
        try:
            export.export_screw(self.obj, path)
        except Exception as exc:
            QtGui.QMessageBox.warning(None, "Export DXF", str(exc))
            return
        App.Console.PrintMessage("HVAC: exported %s\n" % path)

    # -------------------------------------------------------- task dialog
    def getStandardButtons(self):
        return int(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)

    def accept(self):
        if not self._apply():
            return False
        self.doc.recompute()
        self.doc.commitTransaction()
        self._close()
        return True

    def reject(self):
        self.doc.abortTransaction()
        if self.is_new and self.doc.getObject(self.obj.Name):
            sf.delete_children(self.obj)
            self.doc.removeObject(self.obj.Name)
        self.doc.recompute()
        self._close()
        return True

    def _close(self):
        Gui.Control.closeDialog()
        gdoc = Gui.getDocument(self.doc.Name)
        if gdoc and gdoc.getInEdit():
            gdoc.resetEdit()
