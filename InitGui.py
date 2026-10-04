# SPDX-License-Identifier: LGPL-2.1-or-later
# HVAC Fittings workbench - GUI registration.
# Note: FreeCAD exec()s this file, so __file__ is not available here.

import FreeCADGui as Gui


class HVACFittingsWorkbench(Gui.Workbench):
    from hvacdev.freecad import resources as _res
    MenuText = "HVAC Fittings"
    ToolTip = "Flat patterns of sheet-metal duct fittings (neutral surface, DXF output)"
    Icon = _res.icon("HVACFittings.svg")
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


Gui.addWorkbench(HVACFittingsWorkbench())
