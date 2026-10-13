# SPDX-License-Identifier: LGPL-2.1-or-later
import FreeCAD as App
import FreeCADGui as Gui

from hvacdev.freecad import resources


class CmdSegmentedElbow:
    def GetResources(self):
        return {
            "Pixmap": resources.icon("SegmentedElbow.svg"),
            "MenuText": "Segmented elbow",
            "ToolTip": "Flat patterns of a round segmented elbow\n"
                       "(N full middle sections + 2 half end sections)",
        }

    def IsActive(self):
        return not Gui.Control.activeDialog()

    def Activated(self):
        from hvacdev.freecad import elbow_feature as ef
        from hvacdev.freecad.elbow_taskpanel import ElbowTaskPanel
        doc = App.ActiveDocument or App.newDocument("HVAC")
        doc.openTransaction("Segmented elbow")
        obj = ef.make_elbow(doc)
        doc.recompute()
        Gui.Control.showDialog(ElbowTaskPanel(obj, is_new=True))
        Gui.ActiveDocument.ActiveView.viewTop()
        Gui.SendMsgToActiveView("ViewFit")


class CmdRectRoundTransition:
    def GetResources(self):
        return {
            "Pixmap": resources.icon("RectRoundTransition.svg"),
            "MenuText": "Rectangular to round transition",
            "ToolTip": "Flat pattern of a rectangular -> round transition\n"
                       "(rectangle may be off-centre: A, B, E, F)",
        }

    def IsActive(self):
        return not Gui.Control.activeDialog()

    def Activated(self):
        from hvacdev.freecad import transition_feature as tf
        from hvacdev.freecad.transition_taskpanel import TransitionTaskPanel
        doc = App.ActiveDocument or App.newDocument("HVAC")
        doc.openTransaction("Rectangular to round transition")
        obj = tf.make_transition(doc)
        doc.recompute()
        Gui.Control.showDialog(TransitionTaskPanel(obj, is_new=True))
        Gui.ActiveDocument.ActiveView.viewTop()
        Gui.SendMsgToActiveView("ViewFit")


class CmdBranchReducer:
    def GetResources(self):
        return {
            "Pixmap": resources.icon("BranchReducer.svg"),
            "MenuText": "Branch reducer",
            "ToolTip": "Flat patterns of a round reducer with a round branch\n"
                       "(reducer seam through the branch hole, branch seam on its shortest side)",
        }

    def IsActive(self):
        return not Gui.Control.activeDialog()

    def Activated(self):
        from hvacdev.freecad import branch_feature as bf
        from hvacdev.freecad.branch_taskpanel import BranchReducerTaskPanel
        doc = App.ActiveDocument or App.newDocument("HVAC")
        doc.openTransaction("Branch reducer")
        obj = bf.make_branch_reducer(doc)
        doc.recompute()
        Gui.Control.showDialog(BranchReducerTaskPanel(obj, is_new=True))
        Gui.ActiveDocument.ActiveView.viewTop()
        Gui.SendMsgToActiveView("ViewFit")


class CmdFlange:
    def GetResources(self):
        return {
            "Pixmap": resources.icon("Flange.svg"),
            "MenuText": "Flange",
            "ToolTip": "Flat ring flange with arc slots\n(standard sizes from the table, or any size)",
        }

    def IsActive(self):
        return not Gui.Control.activeDialog()

    def Activated(self):
        from hvacdev.freecad import flange_feature as ff
        from hvacdev.freecad.flange_taskpanel import FlangeTaskPanel
        doc = App.ActiveDocument or App.newDocument("HVAC")
        doc.openTransaction("Flange")
        obj = ff.make_flange(doc)
        doc.recompute()
        Gui.Control.showDialog(FlangeTaskPanel(obj, is_new=True))
        Gui.ActiveDocument.ActiveView.viewTop()
        Gui.SendMsgToActiveView("ViewFit")


class CmdThreadFlange:
    def GetResources(self):
        return {
            "Pixmap": resources.icon("ThreadFlange.svg"),
            "MenuText": "Threaded flange",
            "ToolTip": "Flat ring flange with drill & tap cross marks (M6 / M8 / M10 ...)\n"
                       "(standard sizes from the table, or any size)",
        }

    def IsActive(self):
        return not Gui.Control.activeDialog()

    def Activated(self):
        from hvacdev.freecad import flange_thread_feature as tf
        from hvacdev.freecad.flange_thread_taskpanel import ThreadFlangeTaskPanel
        doc = App.ActiveDocument or App.newDocument("HVAC")
        doc.openTransaction("Threaded flange")
        obj = tf.make_thread_flange(doc)
        doc.recompute()
        Gui.Control.showDialog(ThreadFlangeTaskPanel(obj, is_new=True))
        Gui.ActiveDocument.ActiveView.viewTop()
        Gui.SendMsgToActiveView("ViewFit")


class CmdScrewFlight:
    def GetResources(self):
        return {
            "Pixmap": resources.icon("ScrewFlight.svg"),
            "MenuText": "Screw flight",
            "ToolTip": "Blank of a screw conveyor flight for one pitch\n"
                       "(extended to a set gap at the inner edge, number of pieces from L / P)",
        }

    def IsActive(self):
        return not Gui.Control.activeDialog()

    def Activated(self):
        from hvacdev.freecad import screw_feature as sf
        from hvacdev.freecad.screw_taskpanel import ScrewTaskPanel
        doc = App.ActiveDocument or App.newDocument("HVAC")
        doc.openTransaction("Screw flight")
        obj = sf.make_screw(doc)
        doc.recompute()
        Gui.Control.showDialog(ScrewTaskPanel(obj, is_new=True))
        Gui.ActiveDocument.ActiveView.viewTop()
        Gui.SendMsgToActiveView("ViewFit")


def register():
    Gui.addCommand("HVAC_SegmentedElbow", CmdSegmentedElbow())
    Gui.addCommand("HVAC_RectRoundTransition", CmdRectRoundTransition())
    Gui.addCommand("HVAC_BranchReducer", CmdBranchReducer())
    Gui.addCommand("HVAC_Flange", CmdFlange())
    Gui.addCommand("HVAC_ThreadFlange", CmdThreadFlange())
    Gui.addCommand("HVAC_ScrewFlight", CmdScrewFlight())
    return ["HVAC_SegmentedElbow", "HVAC_RectRoundTransition", "HVAC_BranchReducer", "HVAC_Flange",
            "HVAC_ThreadFlange", "HVAC_ScrewFlight"]
