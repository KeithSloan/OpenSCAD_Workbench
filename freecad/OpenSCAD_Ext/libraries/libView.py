from PySide import QtCore, QtGui, QtWidgets
from freecad.OpenSCAD_Ext.libraries.baseLib import BaseOpenSCADBrowser
from freecad.OpenSCAD_Ext.commands import baseSCAD
from freecad.OpenSCAD_Ext.gui.SCAD_Module_Dialog import SCAD_Module_Dialog
from freecad.OpenSCAD_Ext.parsers.parse_scad_for_modules import parse_scad_for_modules
from freecad.OpenSCAD_Ext.commands.baseSCAD import write_log
import FreeCAD
import os


class OpenSCADLibraryBrowser(BaseOpenSCADBrowser):
    """
    Concrete OpenSCAD library browser dialog.
    """

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Tree
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Type"])
        self.tree.setColumnWidth(0, 500)
        layout.addWidget(self.tree)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()

        self.create_btn = QtWidgets.QPushButton("Create SCAD Object")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self.create_scad_object)

        self.edit_btn = QtWidgets.QPushButton("Edit Copy")
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self.edit_copy)

        self.scan_btn = QtWidgets.QPushButton("Scan Modules")
        self.scan_btn.setEnabled(False)
        self.scan_btn.clicked.connect(self.scan_modules)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.close)

        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.scan_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        # Status
        self.status = QtWidgets.QLabel("")
        layout.addWidget(self.status)

    def edit_copy(self):
        if not self.selected_scad:
            return
        write_log("Info", f"Editing copy of {self.selected_scad}")
        baseSCAD.editCopy(self.selected_scad)
        self.status.setText("Opened SCAD file for editing (copy)")

    def scan_modules(self):
        """
        Parse selected SCAD file for documented modules and open SCAD_Module_Dialog.
        """
        if not self.selected_scad or not os.path.isfile(self.selected_scad):
            QtWidgets.QMessageBox.warning(self, "Scan Modules", "No SCAD file selected.")
            return

        write_log("Info", f"Scanning SCAD file: {self.selected_scad}")

        try:
            meta = parse_scad_for_modules(self.selected_scad)
            if not meta["modules"]:
                QtWidgets.QMessageBox.information(
                    self, "Scan Modules", "No documented modules found."
                )
                write_log("Info", "No modules found in SCAD file.")
                return

            dialog = SCAD_Module_Dialog(meta, parent=self)
            dialog.exec_()
            write_log("Info", "ModuleSCAD dialog executed.")

        except Exception as e:
            write_log("Error", f"Module scan failed: {e}")
            QtWidgets.QMessageBox.critical(self, "Scan Modules", f"Error scanning modules:\n{e}")

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
                "App::PropertyFile", "SourceFile", "SCAD", "SCAD source file"
            )

        obj.SourceFile = self.selected_scad
        doc.recompute()

        self.status.setText(f"Created SCAD Object: {name}")
        write_log("Info", f"Created SCAD Object: {name}")

    # Optional: override update_buttons to enable Scan
    def update_buttons(self, enabled):
        self.create_btn.setEnabled(enabled)
        self.edit_btn.setEnabled(enabled)
        self.scan_btn.setEnabled(enabled)

