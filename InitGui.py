# SPDX-License-Identifier: LGPL-2.1-or-later
# HVAC Developments workbench - GUI registration.
# Note: FreeCAD exec()s this file, so __file__ is not available here.

import FreeCADGui as Gui


class HVACDevelopmentsWorkbench(Gui.Workbench):
    from hvacdev.freecad import resources as _res
    MenuText = "HVAC Developments"
    ToolTip = "Flat patterns of sheet-metal duct fittings (neutral surface, DXF output)"
    Icon = _res.icon("HVACDevelopments.svg")
    del _res

    def Initialize(self):
        from hvacdev.freecad import commands
        cmds = commands.register()
        self.appendToolbar("HVAC Fittings", cmds)
        self.appendMenu("HVAC", cmds)

    def Activated(self):
        pass

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(HVACDevelopmentsWorkbench())
