import FreeCAD
import FreeCADGui
import os

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

class BaseParams:

    PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/OpenSCAD"

    @staticmethod
    def _params():
        return FreeCAD.ParamGet(BaseParams.PARAM_PATH)

    @staticmethod
    def editorPathName():
        params = BaseParams._params()
        path = params.GetString('externalEditor')

        write_log("Info", f"Path to external editor {path}")

        if not BaseParams.isValidFilePath(path):
            FreeCAD.Console.PrintError(
                "External editor path is not set or invalid\n"
            )
        return path

    @staticmethod
    def studioPathName():
        params = BaseParams._params()
        path = params.GetString('openscad_studio')

        write_log("Info", f"Path to external openscad_studio {path}")

        if not BaseParams.isValidFilePath(path):
            FreeCAD.Console.PrintError(
                "External editor path is not set or invalid\n"
            )
        return path

    @staticmethod
    def getScadSourcePath():
        params = FreeCAD.ParamGet(
            "User parameter:BaseApp/Preferences/Mod/OpenSCAD"
        )

        path = params.GetString("defaultSourceDirectory", "").strip()

        write_log("Info", f"Path to SCAD Source: {path}")

        # Empty or unset
        if not path:
            FreeCAD.Console.PrintError(
                "Default SCAD Source path is not set in preferences\n"
            )
            return ""

        # Expand ~ and env vars (important on macOS/Linux)
        path = os.path.expanduser(os.path.expandvars(path))

        # Path exists but is not a directory
        if not os.path.isdir(path):
            FreeCAD.Console.PrintError(
                f"Default SCAD Source path is not a valid directory:\n  {path}\n"
            )
            return ""

        return path

    @staticmethod
    def getScadSourcePathOrDefault() -> str:
        """
        Return the configured SCAD source directory, falling back to
        ``<FreeCAD-user-data>/OpenSCAD_Modules`` when the preference is
        not set or points to a non-existent path.

        The fallback directory is created on first use.
        """
        path = BaseParams.getScadSourcePath()
        if path:
            return path

        fallback = os.path.join(
            FreeCAD.getUserAppDataDir(), "OpenSCAD_Modules"
        )
        try:
            os.makedirs(fallback, exist_ok=True)
        except OSError as exc:
            write_log("Warning", f"Could not create fallback SCAD dir {fallback}: {exc}")
        write_log("Info", f"Using fallback SCAD source path: {fallback}")
        return fallback


    # ---- validation helpers ----

    @staticmethod
    def isValidFilePath(path):
        return bool(path) and os.path.isfile(path)

    @staticmethod
    def isValidDirectory(path):
        return bool(path) and os.path.isdir(path)


    def editSource(self, scadPath):
        import os

        name = os.path.basename(scadPath)[0]
        self.editFile(name, scadPath)

    def editFile(self, name, scadPath):
        import subprocess

        editor = BaseParams.editorPathName()   # ✅ CALL IT
        if not editor:
            FreeCAD.Console.PrintError("No external editor configured\n")
            return

        write_log("Info", f"Launching editor for {name}: {scadPath}")
        write_log("Info", f"Launching editor: {editor} {scadPath}")

        subprocess.Popen(
            [editor, scadPath],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    
    def openscad_studio(self, name, scadPath):
        import subprocess

        openscad_studio = BaseParams.studioPathName()   # ✅ CALL IT
        if not openscad_studio:
            FreeCAD.Console.PrintError("No openscad_studio configured\n")
            return

        write_log("Info", f"Launching openscad studio for {name}: {scadPath}")

        subprocess.Popen(
            [openscad_studio, scadPath],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

