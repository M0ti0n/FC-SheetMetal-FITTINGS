# SPDX-License-Identifier: LGPL-2.1-or-later
"""Task panel for the rectangular -> round transition (same layout as the elbow).

    Main Parameters        diagram (A, B, E, F, D, H) + fields
    Manufacturing Options  folding lines [count from N], reference dims, folding labels
    Preview Options        show flat pattern + Generate, add annotations
    Export Options         Export DXF
"""

import os
import re

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from hvacdev.geometry import transition as tg
from hvacdev.freecad import resources
from hvacdev.freecad import transition_feature as tf
from hvacdev.freecad.elbow_taskpanel import _diagram_pixmap, _quantity, _raw, DIAGRAM_WIDTH


class TransitionTaskPanel:
    def __init__(self, obj, is_new):
        self.obj = obj
        self.is_new = is_new
        self.doc = obj.Document
        if not is_new:
            self.doc.openTransaction("Edit transition")
        self.form = [self._main_box(), self._manufacturing_box(),
                     self._preview_box(), self._export_box()]
        self._sync_enabled()

    # ------------------------------------------------------------------ UI
    def _main_box(self):
        o = self.obj
        w = QtGui.QWidget()
        w.setWindowTitle("Main Parameters")
        w.setWindowIcon(QtGui.QIcon(resources.icon("RectRoundTransition.svg")))
        lay = QtGui.QVBoxLayout(w)

        pic = QtGui.QLabel()
        pic.setAlignment(QtCore.Qt.AlignCenter)
        pic.setPixmap(_diagram_pixmap(resources.diagram("transition_rect_round.svg"), DIAGRAM_WIDTH))
        pic.setToolTip("A, B - AB side: rectangle edges left / right of the round centre\n"
                       "E, F - EF side: rectangle edges above / below the round centre\n"
                       "D - diameter of the round end (neutral)\n"
                       "H - height\n"
                       "N - sections per quarter of the round")
        lay.addWidget(pic)

        form = QtGui.QFormLayout()
        self.d = _quantity("mm", o.Diameter.Value, 1.0)
        self.h = _quantity("mm", o.Height.Value, 1.0)
        self.sa = _quantity("mm", o.SideA.Value, 0.1)
        self.sb = _quantity("mm", o.SideB.Value, 0.1)
        self.se = _quantity("mm", o.SideE.Value, 0.1)
        self.sf = _quantity("mm", o.SideF.Value, 0.1)
        self.n = QtGui.QSpinBox()
        self.n.setRange(1, 90)
        self.n.setValue(o.SectionsPerQuarter)
        form.addRow("AB side (A)", self.sa)
        form.addRow("AB side (B)", self.sb)
        form.addRow("EF side (E)", self.se)
        form.addRow("EF side (F)", self.sf)
        form.addRow("Diameter (D)", self.d)
        form.addRow("Height (H)", self.h)
        form.addRow("Sections per quarter (N)", self.n)
        lay.addLayout(form)

        self._bindings = []
        for widget, prop in ((self.sa, "SideA"), (self.sb, "SideB"), (self.se, "SideE"),
                             (self.sf, "SideF"), (self.d, "Diameter"), (self.h, "Height")):
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
        self.fold_n = QtGui.QSpinBox()          # read-only: set by N
        self.fold_n.setRange(0, 9999)
        self.fold_n.setReadOnly(True)
        self.fold_n.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)
        self.fold_n.setToolTip("Number of fold lines = 4 x (N + 1), set by\n"
                               "'Sections per quarter (N)'")
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
        self.cb_anno = QtGui.QCheckBox("Add annotations")
        self.cb_anno.setChecked(o.AddAnnotations)
        self.cb_anno.setToolTip("Triangulation lines and piece name / quantity / parameters")
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

    def _sync_enabled(self, *_):
        self.fold_n.setValue(4 * (self.n.value() + 1))
        self.fold_n.setEnabled(self.cb_fold.isChecked())
        self.cb_labels.setEnabled(self.cb_fold.isChecked())

    # ------------------------------------------------------------- actions
    def _params(self):
        o = self.obj
        return tg.TransitionParams(diameter=_raw(self.d), height=_raw(self.h),
                                   a=_raw(self.sa), b=_raw(self.sb), e=_raw(self.se), f=_raw(self.sf),
                                   sections=self.n.value(), seam=str(o.SeamSide),
                                   fold_lines=self.cb_fold.isChecked(),
                                   fold_mark_length=float(o.FoldMarkLength.Value),
                                   fold_mark_gap=float(o.FoldMarkGap.Value))

    def _apply(self):
        errors = self._params().validate()
        if errors:
            QtGui.QMessageBox.warning(None, "Transition", "\n".join(errors))
            return False
        o = self.obj
        o.Diameter = _raw(self.d)
        o.Height = _raw(self.h)
        o.SideA = _raw(self.sa)
        o.SideB = _raw(self.sb)
        o.SideE = _raw(self.se)
        o.SideF = _raw(self.sf)
        o.SectionsPerQuarter = self.n.value()
        o.AddFoldingLines = self.cb_fold.isChecked()
        o.AddReferenceDimensions = self.cb_dims.isChecked()
        o.AddFoldingLabels = self.cb_labels.isChecked()
        o.ShowFlatPattern = self.cb_show.isChecked()
        o.AddAnnotations = self.cb_anno.isChecked()
        if o.Label.startswith("Transition"):   # keep a name the user typed
            tf.update_label(o)
        return True

    def generate(self):
        if self._apply():
            self.obj.touch()
            self.doc.recompute()
            self._sync_enabled()
            if self.obj.Warning:
                QtGui.QMessageBox.warning(None, "Transition", self.obj.Warning)
            Gui.SendMsgToActiveView("ViewFit")

    def _visibility_changed(self, *_):
        self.obj.ShowFlatPattern = self.cb_show.isChecked()

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
            export.export_transition(self.obj, path)
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
            tf.delete_children(self.obj)
            self.doc.removeObject(self.obj.Name)
        self.doc.recompute()
        self._close()
        return True

    def _close(self):
        Gui.Control.closeDialog()
        gdoc = Gui.getDocument(self.doc.Name)
        if gdoc and gdoc.getInEdit():
            gdoc.resetEdit()
