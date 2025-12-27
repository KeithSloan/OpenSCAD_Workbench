import os
import sys
from PySide import QtWidgets


def ensure_openSCADPATH():
    """
    Ensure OPENSCADPATH is set to a valid default if missing.
    """
    if "OPENSCADPATH" in os.environ:
        return os.environ["OPENSCADPATH"]

    home = os.path.expanduser("~")

    if sys.platform.startswith("win"):
        path = os.path.join(home, "Documents", "OpenSCAD", "libraries")
    elif sys.platform.startswith("darwin"):
        path = os.path.join(home, "Documents", "OpenSCAD", "libraries")
    else:
        path = os.path.join(home, ".local", "share", "OpenSCAD", "libraries")

    os.environ["OPENSCADPATH"] = path
    return path


class BaseOpenSCADBrowser(QtWidgets.QDialog):
    """
    Base dialog class providing directory scanning
    and OPENSCADPATH handling.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("OpenSCAD Library Browser")
        self.resize(700, 500)

        self.openSCADPath = ensure_openSCADPATH()
        self.selected_scad = None

        self.setupUI()
        self.populate()

    def setupUI(self):
        """
        Implemented by subclass.
        """
        raise NotImplementedError

    def populate(self):
        """
        Populate tree widget with OPENSCADPATH contents.
        """
        self.tree.clear()

        if not os.path.isdir(self.openSCADPath):
            return

        self._add_directory(self.openSCADPath, None)

    def _add_directory(self, path, parent_item):
        for name in sorted(os.listdir(path)):
            if name.startswith("."):
                continue

            full = os.path.join(path, name)

            if parent_item is None:
                item = QtWidgets.QTreeWidgetItem(self.tree)
            else:
                item = QtWidgets.QTreeWidgetItem(parent_item)

            item.setText(0, name)

            if os.path.isdir(full):
                item.setText(1, "Folder")
                item.setData(0, 0, full)
                self._add_directory(full, item)
            elif name.lower().endswith(".scad"):
                item.setText(1, "SCAD")
                item.setData(0, 0, full)

    def create_scad_object(self):
        """
        Stub – overridden or connected by caller.
        """
        if not self.selected_scad:
            return

