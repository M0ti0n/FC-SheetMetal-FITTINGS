# SPDX-License-Identifier: LGPL-2.1-or-later
"""Task panel for the flange (same layout as the other tools).

    Main Parameters        diagram + size (A, from the table or typed) + B, M, N, E, T
    Flat Pattern Options   add reference dimensions
    Preview Options        show flat pattern + Generate, add annotations
    Export Options         Export DXF
"""

import os
import re

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from hvacdev.geometry import flange as fg
from hvacdev.geometry.flange_table import SIZES
from hvacdev.freecad import resources
from hvacdev.freecad import flange_feature as ff
from hvacdev.freecad.elbow_taskpanel import _diagram_pixmap, _quantity, _raw, DIAGRAM_WIDTH


def _fmt(v):
    return ("%g" % v)


class FlangeTaskPanel:
    def __init__(self, obj, is_new):
        self.obj = obj
        self.is_new = is_new
        self.doc = obj.Document
        if not is_new:
            self.doc.openTransaction("Edit flange")
        self.form = [self._main_box(), self._pattern_box(), self._preview_box(), self._export_box()]
        self._update_info()

    # ------------------------------------------------------------------ UI
    def _main_box(self):
        o = self.obj
        w = QtGui.QWidget()
        w.setWindowTitle("Main Parameters")
        w.setWindowIcon(QtGui.QIcon(resources.icon("Flange.svg")))
        lay = QtGui.QVBoxLayout(w)

        pic = QtGui.QLabel()
        pic.setAlignment(QtCore.Qt.AlignCenter)
        pic.setPixmap(_diagram_pixmap(resources.diagram("flange.svg"), DIAGRAM_WIDTH))
        pic.setToolTip("A - inner (nominal) diameter\nB - diameter the slots lie on\n"
                       "M - slot width (slots are always 25 mm between end holes)\n"
                       "E - ring width, outer diameter D = A + 2E\n"
                       "N - number of slots, equally spaced\nT - recommended thickness (information)")
        lay.addWidget(pic)

        form = QtGui.QFormLayout()
        self.size = QtGui.QComboBox()
        self.size.setEditable(True)
        self.size.setInsertPolicy(QtGui.QComboBox.NoInsert)
        self.size.addItems([_fmt(r[0]) for r in SIZES])
        self.size.lineEdit().setValidator(QtGui.QDoubleValidator(1.0, 100000.0, 2, self.size))
        self.size.setEditText(_fmt(o.Diameter.Value))
        self.size.setToolTip("Pick a standard size - B, M, N, E and T are filled in from the table.\n"
                             "Type any other A: the values of the nearest smaller standard size are used.\n"
                             "All values can still be changed by hand.")
        self.b = _quantity("mm", o.SlotCircle.Value, 1.0)
        self.m = _quantity("mm", o.SlotWidth.Value, 0.1)
        self.n = QtGui.QSpinBox()
        self.n.setRange(1, 360)
        self.n.setValue(o.SlotCount)
        self.e = _quantity("mm", o.RingWidth.Value, 0.1)
        self.t = _quantity("mm", o.Thickness.Value, 0.0)
        self.info = QtGui.QLabel()
        self.info.setStyleSheet("color: gray;")
        form.addRow("Diameter (A)", self.size)
        form.addRow("Slot circle (B)", self.b)
        form.addRow("Slot width (M)", self.m)
        form.addRow("Number of slots (N)", self.n)
        form.addRow("Ring width (E)", self.e)
        form.addRow("Thickness (T)", self.t)
        form.addRow("", self.info)
        lay.addLayout(form)

        self.size.activated.connect(self._size_chosen)
        self.size.lineEdit().editingFinished.connect(self._size_chosen)
        for wdg in (self.b, self.m, self.e, self.t):
            wdg.valueChanged.connect(self._update_info)
        self.n.valueChanged.connect(self._update_info)
        return w

    def _pattern_box(self):
        w = QtGui.QWidget()
        w.setWindowTitle("Flat Pattern Options")
        g = QtGui.QGridLayout(w)
        self.cb_dims = QtGui.QCheckBox("Add reference dimensions")
        self.cb_dims.setChecked(self.obj.AddReferenceDimensions)
        self.cb_dims.setToolTip("A, B, D, slots and T as text and dimension lines")
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
        self.cb_anno.setToolTip("Centre lines, B circle, hole centres and piece label (with D and T)")
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
        self.cb_anno.toggled.connect(self._annotations_changed)
        self.cb_dims.toggled.connect(self._annotations_changed)
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
    def _a(self):
        try:
            return float(self.size.currentText().replace(",", "."))
        except ValueError:
            return float(self.obj.Diameter.Value)

    def _size_chosen(self, *_):
        p, _std = fg.params_for(self._a())
        for wdg, v in ((self.b, p.b), (self.m, p.m), (self.e, p.e), (self.t, p.t)):
            wdg.setProperty("rawValue", v)
        self.n.setValue(p.n)
        self._update_info()

    def _update_info(self, *_):
        a = self._a()
        d = a + 2 * _raw(self.e)
        std = fg.table_row(a) is not None
        self.info.setText("D = %s mm   (%s)" % (_fmt(d), "standard size" if std else "custom size"))

    def _params(self):
        return fg.FlangeParams(a=self._a(), b=_raw(self.b), m=_raw(self.m), n=self.n.value(),
                               e=_raw(self.e), t=_raw(self.t))

    # ------------------------------------------------------------- actions
    def _apply(self):
        p = self._params()
        errors = p.validate()
        if errors:
            QtGui.QMessageBox.warning(None, "Flange", "\n".join(errors))
            return False
        o = self.obj
        o.Diameter = p.a
        o.SlotCircle = p.b
        o.SlotWidth = p.m
        o.SlotCount = p.n
        o.RingWidth = p.e
        o.Thickness = p.t
        o.AddReferenceDimensions = self.cb_dims.isChecked()
        o.ShowFlatPattern = self.cb_show.isChecked()
        o.AddAnnotations = self.cb_anno.isChecked()
        if o.Label.startswith("Flange"):           # keep a name the user typed
            ff.update_label(o)
        return True

    def generate(self):
        if self._apply():
            self.obj.touch()
            self.doc.recompute()
            Gui.SendMsgToActiveView("ViewFit")

    def _visibility_changed(self, *_):
        self.obj.ShowFlatPattern = self.cb_show.isChecked()

    def _annotations_changed(self, *_):
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
            export.export_flange(self.obj, path)
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
            ff.delete_children(self.obj)
            self.doc.removeObject(self.obj.Name)
        self.doc.recompute()
        self._close()
        return True

    def _close(self):
        Gui.Control.closeDialog()
        gdoc = Gui.getDocument(self.doc.Name)
        if gdoc and gdoc.getInEdit():
            gdoc.resetEdit()
