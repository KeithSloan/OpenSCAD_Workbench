import os
import sys
from PySide import QtCore, QtGui, QtWidgets
import FreeCAD


def ensure_openSCADPATH():
    """
    Ensure OPENSCADPATH is set to the user OpenSCAD libraries folder.
    """
    path = os.environ.get("OPENSCADPATH")
    if path and os.path.exists(path):
        return path

    home = os.path.expanduser("~")

    if sys.platform.startswith("win"):
        default_path = os.path.join(home, "Documents", "OpenSCAD", "libraries")
    elif sys.platform.startswith("darwin"):
        default_path = os.path.join(home, "Documents", "OpenSCAD", "libraries")
    else:
        default_path = os.path.join(home, ".local", "share", "OpenSCAD", "libraries")

    os.makedirs(default_path, exist_ok=True)
    os.environ["OPENSCADPATH"] = default_path
    return default_path


class BaseOpenSCADBrowser(QtWidgets.QDialog):
    """
    Base OpenSCAD library browser.

    Provides:
      - Tree navigation
      - SCAD file selection
      - Create / Edit / Scan Modules actions
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("OpenSCAD Library Browser")
        self.resize(800, 500)

        ensure_openSCADPATH()
        self.openSCADPath = os.environ.get("OPENSCADPATH")

        if not self.openSCADPath or not os.path.exists(self.openSCADPath):
            QtWidgets.QMessageBox.critical(
                self, "Error", "OPENSCADPATH not set or invalid"
            )
            self.close()
            return

        self.selected_scad = None

        self.setupUI()
        self.load_top_level()

    # -------------------------------------------------
    # UI
    # -------------------------------------------------
    def setupUI(self):
        """
        Shared UI for all OpenSCAD library browsers.
        Subclasses may extend but should not replace.
        """
        layout = QtWidgets.QVBoxLayout(self)

        # -------------------------------
        # Tree
        # -------------------------------
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Type"])
        self.tree.setColumnWidth(0, 500)
        layout.addWidget(self.tree)

        # -------------------------------
        # Buttons
        # -------------------------------
        self.btn_layout = QtWidgets.QHBoxLayout()

        self.create_btn = QtWidgets.QPushButton("Create SCAD Object")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self.create_scad_object)

        self.scan_btn = QtWidgets.QPushButton("Scan Modules")
        self.scan_btn.setEnabled(False)
        self.scan_btn.clicked.connect(self.scan_modules)

        self.edit_btn = QtWidgets.QPushButton("Edit Copy")
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self.edit_copy)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.close)

        self.btn_layout.addWidget(self.create_btn)
        self.btn_layout.addWidget(self.scan_btn)
        self.btn_layout.addWidget(self.edit_btn)
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(close_btn)

        layout.addLayout(self.btn_layout)

        # -------------------------------
        # Status
        # -------------------------------
        self.status = QtWidgets.QLabel("")
        layout.addWidget(self.status)

    # -------------------------------------------------
    # Tree population
    # -------------------------------------------------
    def load_top_level(self):
        self.tree.clear()

        for name in sorted(os.listdir(self.openSCADPath)):
            if name.startswith("."):
                continue

            full_path = os.path.join(self.openSCADPath, name)

            if os.path.isdir(full_path):
                item = QtWidgets.QTreeWidgetItem([name, "Directory"])
                item.setData(0, QtCore.Qt.UserRole, full_path)
                self.tree.addTopLevelItem(item)
                QtWidgets.QTreeWidgetItem(item, ["Loading...", ""])

            elif name.lower().endswith(".scad"):
                base = os.path.splitext(name)[0]
                item = QtWidgets.QTreeWidgetItem([base, "SCAD File"])
                item.setData(0, QtCore.Qt.UserRole, full_path)
                item.setToolTip(0, full_path)
                self.tree.addTopLevelItem(item)

        self.tree.itemExpanded.connect(self.on_item_expanded)
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)

    def on_item_expanded(self, item):
        path = item.data(0, QtCore.Qt.UserRole)

        if not os.path.isdir(path):
            return

        if item.childCount() == 1 and item.child(0).text(0) == "Loading...":
            item.takeChildren()

            for name in sorted(os.listdir(path)):
                if name.startswith("."):
                    continue

                full_path = os.path.join(path, name)

                if os.path.isdir(full_path):
                    child = QtWidgets.QTreeWidgetItem([name, "Directory"])
                    child.setData(0, QtCore.Qt.UserRole, full_path)
                    item.addChild(child)
                    QtWidgets.QTreeWidgetItem(child, ["Loading...", ""])

                elif name.lower().endswith(".scad"):
                    base = os.path.splitext(name)[0]
                    child = QtWidgets.QTreeWidgetItem([base, "SCAD File"])
                    child.setData(0, QtCore.Qt.UserRole, full_path)
                    child.setToolTip(0, full_path)
                    item.addChild(child)

    # -------------------------------------------------
    # Selection handling
    # -------------------------------------------------
    def on_selection_changed(self):
        self.selected_scad = None

        items = self.tree.selectedItems()
        if not items:
            self.update_buttons(False)
            return

        item = items[0]
        path = item.data(0, QtCore.Qt.UserRole)

        if path and os.path.isfile(path) and path.lower().endswith(".scad"):
            self.selected_scad = path
            self.update_buttons(True)
        else:
            self.update_buttons(False)

    def update_buttons(self, enabled):
        self.create_btn.setEnabled(enabled)
        self.edit_btn.setEnabled(enabled)
        self.scan_btn.setEnabled(enabled)

    # -------------------------------------------------
    # Actions
    # -------------------------------------------------
    def create_scad_object(self):
        if not self.selected_scad:
            return

        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("SCAD_Import")

        name = os.path.splitext(os.path.basename(self.selected_scad))[0]
        obj = doc.addObject("Part::FeaturePython", name)
        obj.Label = name

        if not hasattr(obj, "SourceFile"):
            obj.addProperty(
                "App::PropertyFile",
                "SourceFile",
                "SCAD",
                "SCAD source file",
            )

        obj.SourceFile = self.selected_scad
        doc.recompute()

        self.status.setText(f"Created SCAD Object: {name}")

    def edit_copy(self):
        """
        Intended to be implemented by subclass.
        """
        FreeCAD.Console.PrintWarning(
            "Edit Copy not implemented in base class\n"
        )

    def scan_modules(self):
        """
        Invoke SCAD module scanning via FreeCAD command,
        passing the currently selected SCAD file.
        """
        if not self.selected_scad:
            QtWidgets.QMessageBox.warning(
                self, "Scan Modules", "No SCAD file selected!"
            )
            return

        try:
            import FreeCADGui
            FreeCADGui.runCommand(
                "ModuleSCAD_CMD",
                {"scad_library": self.selected_scad}  # <-- MUST pass here
            )
            self.status.setText(f"Scanning SCAD modules: {os.path.basename(self.selected_scad)}")
        except Exception as e:
            FreeCAD.Console.PrintError(f"Module scan failed: {e}\n")

