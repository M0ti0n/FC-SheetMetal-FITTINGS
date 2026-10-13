# SPDX-License-Identifier: LGPL-2.1-or-later
"""Task panel for the reducer with branch (same layout as the elbow).

    Main Parameters        diagram (D1, D2, H1, H2, D3, L, A) + fields
    Flat Pattern Options   folding lines [n], reference dims, folding labels
    Preview Options        show flat pattern + Generate; Reducer / Branch; add annotations
    Export Options         Export DXF
"""

import os
import re

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from hvacdev.geometry import branch_reducer as bg
from hvacdev.freecad import resources
from hvacdev.freecad import branch_feature as bf
from hvacdev.freecad.elbow_taskpanel import _diagram_pixmap, _quantity, _raw, DIAGRAM_WIDTH


class BranchReducerTaskPanel:
    def __init__(self, obj, is_new):
        self.obj = obj
        self.is_new = is_new
        self.doc = obj.Document
        if not is_new:
            self.doc.openTransaction("Edit branch reducer")
        self.form = [self._main_box(), self._pattern_box(),
                     self._preview_box(), self._export_box()]
        self._sync_enabled()

    # ------------------------------------------------------------------ UI
    def _main_box(self):
        o = self.obj
        w = QtGui.QWidget()
        w.setWindowTitle("Main Parameters")
        w.setWindowIcon(QtGui.QIcon(resources.icon("BranchReducer.svg")))
        lay = QtGui.QVBoxLayout(w)

        pic = QtGui.QLabel()
        pic.setAlignment(QtCore.Qt.AlignCenter)
        pic.setPixmap(_diagram_pixmap(resources.diagram("reducer_branch.svg"), DIAGRAM_WIDTH))
        pic.setToolTip("D1 - reducer diameter at the top\nD2 - reducer diameter at the bottom\n"
                       "H1 - reducer height\nH2 - height where the branch axis meets the reducer\n"
                       "D3 - branch diameter\nL - from the reducer along the branch axis to its end\n"
                       "A - branch angle above the horizontal")
        lay.addWidget(pic)

        form = QtGui.QFormLayout()
        self.d1 = _quantity("mm", o.DiameterTop.Value, 1.0)
        self.d2 = _quantity("mm", o.DiameterBottom.Value, 1.0)
        self.h1 = _quantity("mm", o.Height.Value, 1.0)
        self.h2 = _quantity("mm", o.BranchHeight.Value, 0.1)
        self.d3 = _quantity("mm", o.BranchDiameter.Value, 1.0)
        self.ln = _quantity("mm", o.BranchLength.Value, 1.0)
        self.an = _quantity("deg", o.BranchAngle.Value, -89.0, 89.9)
        form.addRow("Top diameter (D1)", self.d1)
        form.addRow("Bottom diameter (D2)", self.d2)
        form.addRow("Height (H1)", self.h1)
        form.addRow("Branch height (H2)", self.h2)
        form.addRow("Branch diameter (D3)", self.d3)
        form.addRow("Branch length (L)", self.ln)
        form.addRow("Branch angle (A)", self.an)
        lay.addLayout(form)

        self._bindings = []
        for widget, prop in ((self.d1, "DiameterTop"), (self.d2, "DiameterBottom"), (self.h1, "Height"),
                             (self.h2, "BranchHeight"), (self.d3, "BranchDiameter"),
                             (self.ln, "BranchLength"), (self.an, "BranchAngle")):
            try:
                b = Gui.ExpressionBinding(widget)
                b.bind(o, prop)
                self._bindings.append(b)
            except Exception:
                pass
        return w

    def _pattern_box(self):
        o = self.obj
        w = QtGui.QWidget()
        w.setWindowTitle("Flat Pattern Options")
        g = QtGui.QGridLayout(w)
        self.cb_fold = QtGui.QCheckBox("Add folding lines")
        self.cb_fold.setChecked(o.AddFoldingLines)
        self.fold_n = QtGui.QSpinBox()
        self.fold_n.setRange(1, 720)
        self.fold_n.setValue(o.FoldingLineCount)
        self.fold_n.setToolTip("Number of folding lines around the reducer\n"
                               "and around the branch")
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
        self.cb_red = QtGui.QCheckBox("Reducer")
        self.cb_red.setChecked(o.ShowReducer)
        self.cb_br = QtGui.QCheckBox("Branch")
        self.cb_br.setChecked(o.ShowBranch)
        self.cb_anno = QtGui.QCheckBox("Add annotations")
        self.cb_anno.setChecked(o.AddAnnotations)
        self.cb_anno.setToolTip("Reference generators and piece name / quantity / parameters")
        gen = QtGui.QPushButton("Generate")
        gen.setDefault(False)
        gen.setAutoDefault(False)
        g.addWidget(self.cb_show, 0, 0)
        g.addWidget(gen, 0, 1)
        g.addWidget(self.cb_red, 1, 0)
        g.addWidget(self.cb_br, 2, 0)
        g.addWidget(self.cb_anno, 3, 0)
        for cb in (self.cb_red, self.cb_br):
            cb.setStyleSheet("margin-left: 22px;")
        g.setContentsMargins(9, 9, 9, 9)
        g.setColumnStretch(0, 1)
        gen.clicked.connect(self.generate)
        for cb in (self.cb_show, self.cb_red, self.cb_br):
            cb.toggled.connect(self._visibility_changed)
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
        if hasattr(self, "cb_red"):
            self.cb_red.setEnabled(self.cb_show.isChecked())
            self.cb_br.setEnabled(self.cb_show.isChecked())

    # ------------------------------------------------------------- actions
    def _params(self):
        o = self.obj
        return bg.BranchReducerParams(
            d1=_raw(self.d1), d2=_raw(self.d2), h1=_raw(self.h1), h2=_raw(self.h2),
            d3=_raw(self.d3), length=_raw(self.ln), angle=_raw(self.an),
            fold_lines=self.fold_n.value() if self.cb_fold.isChecked() else 0,
            fold_mark_length=float(o.FoldMarkLength.Value), fold_mark_gap=float(o.FoldMarkGap.Value))

    def _apply(self):
        p = self._params()
        errors = p.validate()
        if not errors:
            try:
                bg.develop(p)                      # catches a branch that does not fit
            except ValueError as exc:
                errors = [str(exc)]
        if errors:
            QtGui.QMessageBox.warning(None, "Branch reducer", "\n".join(errors))
            return False
        o = self.obj
        o.DiameterTop = _raw(self.d1)
        o.DiameterBottom = _raw(self.d2)
        o.Height = _raw(self.h1)
        o.BranchHeight = _raw(self.h2)
        o.BranchDiameter = _raw(self.d3)
        o.BranchLength = _raw(self.ln)
        o.BranchAngle = _raw(self.an)
        o.AddFoldingLines = self.cb_fold.isChecked()
        o.FoldingLineCount = self.fold_n.value()
        o.AddReferenceDimensions = self.cb_dims.isChecked()
        o.AddFoldingLabels = self.cb_labels.isChecked()
        o.ShowFlatPattern = self.cb_show.isChecked()
        o.ShowReducer = self.cb_red.isChecked()
        o.ShowBranch = self.cb_br.isChecked()
        o.AddAnnotations = self.cb_anno.isChecked()
        if o.Label.startswith("Branch reducer"):   # keep a name the user typed
            bf.update_label(o)
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
        self.obj.ShowReducer = self.cb_red.isChecked()
        self.obj.ShowBranch = self.cb_br.isChecked()

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
            sections = export.export_branch_reducer(self.obj, path)
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
        # remember the name first: aborting the transaction deletes a new object,
        # and a deleted object must not be touched any more
        name = self.obj.Name
        self.doc.abortTransaction()
        if self.is_new:
            obj = self.doc.getObject(name)      # still there e.g. when undo is switched off
            if obj is not None:
                bf.delete_children(obj)
                self.doc.removeObject(name)
        self.doc.recompute()
        self._close()
        return True

    def _close(self):
        Gui.Control.closeDialog()
        gdoc = Gui.getDocument(self.doc.Name)
        if gdoc and gdoc.getInEdit():
            gdoc.resetEdit()
