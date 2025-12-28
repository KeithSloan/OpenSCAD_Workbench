import FreeCAD as App
import FreeCADGui as Gui
import sys

# Register logger - Must be in Gui and outside of Workbench
from .logger.Workbench_logger import init as init_logging
#from freecad.OpenSCAD_Ext.logger.Workbench_logger import init as init_logging

init_logging()

class OpenSCADWorkbench_Ext(Gui.Workbench):
    """External OpenSCAD Workbench"""
    MenuText = "OpenSCAD_Ext"
    ToolTip = "External replacement for legacy OpenSCAD tools"
    Icon = "OpenSCAD_Ext.svg"

    "OpenSCAD workbench object"

    def Initialize(self):
        def QT_TRANSLATE_NOOP(scope, text):
                return text
        App.Console.PrintMessage("✅ OpenSCADWorkbench_Ext.Initialize()\n")

	    # Resource locations for new-style workbenches
        Gui.addIconPath(":/icons")
        Gui.addLanguagePath(":/translations")

    	# Register preferences (new FreeCAD 1.0 API)
        # from . import preferences
        # preferences.Load()

        # Register logger - Must be in Gui and outside of Workbench
        from .logger.Workbench_logger import init as init_logging
        #from freecad.OpenSCAD_Ext.logger.Workbench_logger import init as init_logging

        init_logging()


        # TODO: add commands when ready
        # self.appendToolbar("OpenSCAD Tools", [...])
        # self.appendMenu("OpenSCAD", [...])

        # NOTE:
        # DO NOT call addPreferencePage here — new-style workbenches
        # must use addPreferencePageProvider in preferences.py
        # (If missing, FreeCAD shows the “not a preference page” errors)

        from .commands import newSCAD
        from .commands import editSCAD
        from .commands import renderSCAD
        from .commands import varsSCAD
        from .commands import librarySCAD
        from .commands import moduleSCAD
 
        commands = [
            "NewSCADFileObject_CMD",
            "EditSCADFileObject_CMD",
            "RenderSCADFileObject_CMD",
            "VarsSCADFileObject_CMD",
            "LibrarySCAD_CMD",
            "ModuleSCAD_CMD",

        ]
        toolbarcommands = commands

        '''
        Old Commands
        import OpenSCAD_rc, OpenSCADCommands

        commands = [
            "OpenSCAD_ReplaceObject",
            "OpenSCAD_RemoveSubtree",
            "OpenSCAD_RefineShapeFeature",
            "OpenSCAD_MirrorMeshFeature",
            "OpenSCAD_ScaleMeshFeature",
            "OpenSCAD_ResizeMeshFeature",
            "OpenSCAD_IncreaseToleranceFeature",
            "OpenSCAD_Edgestofaces",
            "OpenSCAD_ExpandPlacements",
            "OpenSCAD_ExplodeGroup",
        ]
        toolbarcommands = [
            "OpenSCAD_ReplaceObject",
            "OpenSCAD_RemoveSubtree",
            "OpenSCAD_ExplodeGroup",
            "OpenSCAD_RefineShapeFeature",
            "OpenSCAD_IncreaseToleranceFeature",
        ]
        import PartGui

        parttoolbarcommands = [
            "Part_CheckGeometry",
            "Part_Primitives",
            "Part_Builder",
            "Part_Cut",
            "Part_Fuse",
            "Part_Common",
            "Part_Extrude",
            "Part_Revolve",
        ]
        import FreeCAD
        translate = FreeCAD.Qt.translate
        '''
        param = App.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD")
        openscadfilename = param.GetString("openscadexecutable")
        if not openscadfilename:
            import OpenSCADUtils

            openscadfilename = OpenSCADUtils.searchforopenscadexe()
            if openscadfilename:  # automatic search was successful
                App.addImportType("OpenSCAD Format (*.scad *.SCAD)", "importCSG")
                param.SetString(
                    "openscadexecutable", openscadfilename
                )  # save the result
        ''' 
        if openscadfilename:
            commands.extend(
                [
                    "OpenSCAD_AddOpenSCADElement",
                    "OpenSCAD_MeshBoolean",
                    "OpenSCAD_Hull",
                    "OpenSCAD_Minkowski",
                ]
            )

            toolbarcommands.extend(
                [
                    "OpenSCAD_AddOpenSCADElement",
                    "OpenSCAD_MeshBoolean",
                    "OpenSCAD_Hull",
                    "OpenSCAD_Minkowski",
                ]
            )
        else:
            App.Console.PrintWarning("OpenSCAD executable not found\n")
        '''
        transferMechanism = param.GetInt("transfermechanism", 0)
        if openscadfilename and transferMechanism == 0:
            # We are using the Python temp-directory creation function
            if "snap" in openscadfilename:
                App.Console.PrintMessage(
                    translate(
                        "OpenSCAD",
                        "It looks like you may be using a Snap version of OpenSCAD.",
                    )
                    + " "
                    + translate(
                        "OpenSCAD",
                        "If OpenSCAD execution fails to load the temporary file, use FreeCAD's OpenSCAD Workbench Preferences to change the transfer mechanism.",
                    )
                    + "\n"
                )
            elif sys.executable.startswith("/tmp/"):  # Heuristic for AppImages
                App.Console.PrintMessage(
                    translate(
                        "OpenSCAD",
                        "It looks like you may be using a sandboxed version of FreeCAD.",
                    )
                    + " "
                    + translate(
                        "OpenSCAD",
                        "If OpenSCAD execution fails to load the temporary file, use FreeCAD's OpenSCAD Workbench Preferences to change the transfer mechanism.",
                    )
                    + "\n"
                )
        
        self.appendToolbar(
            QT_TRANSLATE_NOOP("Workbench", "OpenSCAD Tools"), toolbarcommands
        )
        #self.appendMenu("OpenSCAD", commands)
        #self.appendToolbar(
        #    QT_TRANSLATE_NOOP("Workbench", "Frequently-used Part WB tools"), parttoolbarcommands
        #)
        # self.appendMenu('OpenSCAD',["AddOpenSCADElement"])
        ###self.appendCommandbar("&Generic Tools",["ColorCodeShape"])
        Gui.addIconPath(":/icons")
        Gui.addLanguagePath(":/translations")

        ### Change when 1.0.2 supports new Addpreference
        ### Gui.addPreferencePage(":/ui/openscadprefs-base.ui", "OpenSCAD_Ext")
        import os
        import freecad.OpenSCAD_Ext as OpenSCAD_Ext

        # Directory where the module (__init__.py) lives
        module_dir = os.path.dirname(OpenSCAD_Ext.__file__)

        # Workbench’s Resources directory
        resource_dir = os.path.join(module_dir, "Resources")
        print(resource_dir)
        prefs_ui = os.path.join(resource_dir, "ui", "OpenSCAD_Ext_Preferences.ui")
        Gui.addPreferencePage(prefs_ui, "OpenSCAD_Ext")

    def Activated(self):
        App.Console.PrintMessage("✅ OpenSCADWorkbench_Ext.Activated()\n")

    def Deactivated(self):
        App.Console.PrintMessage("✅ OpenSCADWorkbench_Ext.Deactivated()\n")

    def GetClassName(self):
        return "Gui::PythonWorkbench"

# Register the workbench
Gui.addWorkbench(OpenSCADWorkbench_Ext())
App.Console.PrintMessage("✅ OpenSCAD_Ext registered\n")
