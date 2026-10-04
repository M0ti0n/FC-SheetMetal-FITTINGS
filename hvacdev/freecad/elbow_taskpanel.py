# SPDX-License-Identifier: LGPL-2.1-or-later
"""Task panel for the segmented elbow (layout follows the agreed mockup).

    Main Parameters        diagram (D, A, R, N, B) + 4 fields
    Manufacturing Options  folding lines [n], reference dims, folding labels
    Preview Options        show flat pattern / middle (N) / end (B) + Generate
    Export Options         Export DXF
"""

import os
import re

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from hvacdev.geometry import elbow as eg
from hvacdev.freecad import resources
from hvacdev.freecad import elbow_feature as ef

DIAGRAM_WIDTH = 290


def _diagram_pixmap(path, width):
    """Render the SVG crisply at the panel width (HiDPI aware)."""
    try:
        from PySide import QtSvg
        renderer = QtSvg.QSvgRenderer(path)
        size = renderer.defaultSize()
        height = int(width * size.height() / max(1, size.width()))
        ratio = QtGui.QApplication.instance().devicePixelRatio() if hasattr(
            QtGui.QApplication.instance(), "devicePixelRatio") else 1.0
        pm = QtGui.QPixmap(int(width * ratio), int(height * ratio))
        pm.fill(QtCore.Qt.white)
        painter = QtGui.QPainter(pm)
        renderer.render(painter)
        painter.end()
        pm.setDevicePixelRatio(ratio)
        return pm
    except Exception:
        return QtGui.QPixmap(path).scaledToWidth(width, QtCore.Qt.SmoothTransformation)


def _quantity(unit, value, minimum=0.0, maximum=1e6, decimals=2):
    w = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
    w.setProperty("unit", unit)
    w.setProperty("minimum", minimum)
    w.setProperty("maximum", maximum)
    w.setProperty("decimals", decimals)
    w.setProperty("rawValue", value)
    return w


def _raw(w):
    return float(w.property("rawValue"))


class ElbowTaskPanel:
    def __init__(self, obj, is_new):
        self.obj = obj
        self.is_new = is_new
        self.doc = obj.Document
        if not is_new:
            self.doc.openTransaction("Edit segmented elbow")
        self.form = [self._main_box(), self._manufacturing_box(),
                     self._preview_box(), self._export_box()]
        self._sync_enabled()

    # ------------------------------------------------------------------ UI
    def _main_box(self):
        o = self.obj
        w = QtGui.QWidget()
        w.setWindowTitle("Main Parameters")
        w.setWindowIcon(QtGui.QIcon(resources.icon("SegmentedElbow.svg")))
        lay = QtGui.QVBoxLayout(w)

        pic = QtGui.QLabel()
        pic.setAlignment(QtCore.Qt.AlignCenter)
        pic.setPixmap(_diagram_pixmap(resources.diagram("elbow.svg"), DIAGRAM_WIDTH))
        pic.setToolTip("D - diameter (neutral)\nA - elbow angle\nR - centreline radius\n"
                       "N - number of full middle sections\nB - end section (= half of a middle section)")
        lay.addWidget(pic)

        form = QtGui.QFormLayout()
        self.d = _quantity("mm", o.Diameter.Value, 1.0)
        self.a = _quantity("deg", o.Angle.Value, 1.0, 179.0)
        self.r = _quantity("mm", o.Radius.Value, 1.0)
        self.n = QtGui.QSpinBox()
        self.n.setRange(0, 99)
        self.n.setValue(o.MiddleSections)
        form.addRow("Diameter (D)", self.d)
        form.addRow("Elbow angle (A)", self.a)
        form.addRow("Centreline radius (R)", self.r)
        form.addRow("Number of middle sections (N)", self.n)
        lay.addLayout(form)

        # "fx" expression buttons, like any native FreeCAD panel
        self._bindings = []   # keep references, or Qt/Python drops them
        for widget, prop in ((self.d, "Diameter"), (self.a, "Angle"), (self.r, "Radius")):
            try:
                b = Gui.ExpressionBinding(widget)
                b.bind(o, prop)
                self._bindings.append(b)
            except Exception:
                pass
        self.n.valueChanged.connect(self._sync_enabled)
        return w

    def _manufacturing_box(self):
        o = self.obj
        w = QtGui.QWidget()
        w.setWindowTitle("Manufacturing Options")
        g = QtGui.QGridLayout(w)
        self.cb_fold = QtGui.QCheckBox("Add folding lines")
        self.cb_fold.setChecked(o.AddFoldingLines)
        self.fold_n = QtGui.QSpinBox()
        self.fold_n.setRange(1, 720)
        self.fold_n.setValue(o.FoldingLineCount)
        self.fold_n.setToolTip("Number of folding lines around the circumference.\n"
                               "Bend angle per fold = 360 / number")
        self.cb_dims = QtGui.QCheckBox("Add reference dimensions")
        self.cb_dims.setChecked(o.AddReferenceDimensions)
        self.cb_labels = QtGui.QCheckBox("Add folding labels")
        self.cb_labels.setChecked(o.AddFoldingLabels)
        g.addWidget(self.cb_fold, 0, 0)
        g.addWidget(self.fold_n, 0, 1)
        g.addWidget(self.cb_dims, 1, 0, 1, 2)
        g.addWidget(self.cb_labels, 2, 0, 1, 2)
        g.setColumnStretch(0, 1)
        self.cb_fold.toggled.connect(self._sync_enabled)
        return w

    def _preview_box(self):
        o = self.obj
        w = QtGui.QWidget()
        w.setWindowTitle("Preview Options")
        g = QtGui.QGridLayout(w)
        self.cb_show = QtGui.QCheckBox("Show flat pattern")
        self.cb_show.setChecked(o.ShowFlatPattern)
        self.cb_mid = QtGui.QCheckBox("Middle sec. (N)")
        self.cb_mid.setChecked(o.ShowMiddle)
        self.cb_end = QtGui.QCheckBox("End sec. (B)")
        self.cb_end.setChecked(o.ShowEnd)
        self.cb_anno = QtGui.QCheckBox("Add annotations")
        self.cb_anno.setChecked(o.AddAnnotations)
        self.cb_anno.setToolTip("Reference lines (heel / side / throat, mid-plane)\n"
                                "and piece name / quantity / parameters")
        gen = QtGui.QPushButton("Generate")
        gen.setDefault(False)
        gen.setAutoDefault(False)
        g.addWidget(self.cb_show, 0, 0)
        g.addWidget(gen, 0, 1)
        g.addWidget(self.cb_mid, 1, 0)
        g.addWidget(self.cb_end, 2, 0)
        g.addWidget(self.cb_anno, 3, 0)
        g.setContentsMargins(9, 9, 9, 9)
        for cb in (self.cb_mid, self.cb_end):
            cb.setStyleSheet("margin-left: 22px;")
        g.setColumnStretch(0, 1)
        gen.clicked.connect(self.generate)
        # visibility toggles are instant, no regeneration needed
        self.cb_show.toggled.connect(self._visibility_changed)
        self.cb_mid.toggled.connect(self._visibility_changed)
        self.cb_end.toggled.connect(self._visibility_changed)
        # annotations change the generated content -> quick regenerate
        self.cb_anno.toggled.connect(self._annotations_changed)
        return w

    def _export_box(self):
        w = QtGui.QWidget()
        w.setWindowTitle("Export Options")
        lay = QtGui.QHBoxLayout(w)
        btn = QtGui.QPushButton("Export DXF")
        btn.setAutoDefault(False)
        btn.setToolTip("Exports exactly the flat patterns visible in the model space")
        lay.addStretch(1)
        lay.addWidget(btn)
        btn.clicked.connect(self.export_dxf)
        return w

    def _sync_enabled(self, *_):
        self.fold_n.setEnabled(self.cb_fold.isChecked())
        self.cb_labels.setEnabled(self.cb_fold.isChecked())
        self.cb_mid.setEnabled(self.cb_show.isChecked() and self.n.value() > 0)
        self.cb_end.setEnabled(self.cb_show.isChecked())

    # ------------------------------------------------------------- actions
    def _params(self):
        return eg.ElbowParams(diameter=_raw(self.d), angle=_raw(self.a), radius=_raw(self.r),
                              middle_sections=self.n.value(),
                              fold_lines=self.fold_n.value() if self.cb_fold.isChecked() else 0,
                              seam=str(self.obj.SeamPosition),
                              fold_mark_length=float(self.obj.FoldMarkLength.Value),
                              fold_mark_gap=float(self.obj.FoldMarkGap.Value))

    def _apply(self):
        """Write panel values to the object. Returns False on invalid input."""
        errors = self._params().validate()
        if errors:
            QtGui.QMessageBox.warning(None, "Segmented elbow", "\n".join(errors))
            return False
        o = self.obj
        o.Diameter = _raw(self.d)
        o.Angle = _raw(self.a)
        o.Radius = _raw(self.r)
        o.MiddleSections = self.n.value()
        o.AddFoldingLines = self.cb_fold.isChecked()
        o.FoldingLineCount = self.fold_n.value()
        o.AddReferenceDimensions = self.cb_dims.isChecked()
        o.AddFoldingLabels = self.cb_labels.isChecked()
        o.ShowFlatPattern = self.cb_show.isChecked()
        o.ShowMiddle = self.cb_mid.isChecked()
        o.ShowEnd = self.cb_end.isChecked()
        o.AddAnnotations = self.cb_anno.isChecked()
        if o.Label.startswith("Elbow"):   # keep a name the user typed
            ef.update_label(o)
        return True

    def generate(self):
        if self._apply():
            self.obj.touch()
            self.doc.recompute()
            self._sync_enabled()
            Gui.SendMsgToActiveView("ViewFit")

    def _visibility_changed(self, *_):
        self._sync_enabled()
        self.obj.ShowFlatPattern = self.cb_show.isChecked()
        self.obj.ShowMiddle = self.cb_mid.isChecked()
        self.obj.ShowEnd = self.cb_end.isChecked()

    def _annotations_changed(self, checked):
        self.obj.AddAnnotations = checked
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
            sections = export.export_elbow(self.obj, path)
        except Exception as exc:
            QtGui.QMessageBox.warning(None, "Export DXF", str(exc))
            return
        App.Console.PrintMessage("HVAC: exported %s (%s)\n" % (path, ", ".join(sections)))

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
            ef.delete_children(self.obj)
            self.doc.removeObject(self.obj.Name)
        self.doc.recompute()
        self._close()
        return True

    def _close(self):
        Gui.Control.closeDialog()
        gdoc = Gui.getDocument(self.doc.Name)
        if gdoc and gdoc.getInEdit():
            gdoc.resetEdit()
