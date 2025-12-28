import os
import shutil
from PySide import QtWidgets
import FreeCAD
import FreeCADGui

from .baseLib import BaseOpenSCADBrowser


class OpenSCADLibraryBrowser(BaseOpenSCADBrowser):
    """
    OpenSCAD Library Browser implementation.

    Uses BaseOpenSCADBrowser for UI and logic,
    implements Edit Copy behaviour.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OpenSCAD Library Browser")

    # -------------------------------------------------
    # Edit Copy implementation
    # -------------------------------------------------
    def edit_copy(self):
        """
        Copy selected SCAD file into user workspace
        and open it in the editor.
        """
        if not self.selected_scad:
            return

        src = self.selected_scad

        # Destination: user OpenSCAD working directory
        user_dir = FreeCAD.ParamGet(
            "User parameter:BaseApp/Preferences/General"
        ).GetString("FilePath", "")

        if not user_dir or not os.path.isdir(user_dir):
            user_dir = os.path.expanduser("~/Documents/OpenSCAD")

        os.makedirs(user_dir, exist_ok=True)

        base = os.path.basename(src)
        dst = os.path.join(user_dir, base)

        # Avoid overwrite
        if os.path.exists(dst):
            name, ext = os.path.splitext(base)
            i = 1
            while True:
                candidate = f"{name}_{i}{ext}"
                dst = os.path.join(user_dir, candidate)
                if not os.path.exists(dst):
                    break
                i += 1

        try:
            shutil.copy(src, dst)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Copy Failed", str(e)
            )
            return

        # Open in FreeCAD editor
        try:
            FreeCADGui.open(dst)
        except Exception:
            pass

        self.status.setText(f"Editing copy: {os.path.basename(dst)}")

