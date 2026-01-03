import os
import FreeCAD
from PySide import QtWidgets, QtCore

from freecad.OpenSCAD_Ext.libraries.ensure_openSCADPATH import ensure_openSCADPATH
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.objects.SCADObject import createSCADObject
from freecad.OpenSCAD_Ext.parsers.parse_scad_for_modules import parse_scad_for_modules
from freecad.OpenSCAD_Ext.gui.SCAD_Module_Dialog import SCAD_Module_Dialog

class OpenSCADLibraryBrowser(QtWidgets.QDialog):
    """
    OpenSCAD Library Browser dialog.
    Displays directories and SCAD files in OPENSCADPATH.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OpenSCAD Library Browser")
        self.resize(700, 500)
        self.selected_item = None
        self.selected_scad = None
        self.selected_dir = None

        self.setupUI()
        self.populate_tree()

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Tree
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Type"])
        self.tree.setColumnWidth(0, 500)
        self.tree.itemClicked.connect(self.on_item_clicked)
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

    def populate_tree(self, path=None, parent_item=None):
        if path is None:
            path = ensure_openSCADPATH()
            write_log("Info", f"Displaying SCAD library directory: {path}")

        try:
            entries = os.listdir(path)
        except Exception as e:
            write_log("Error", f"Cannot list folder {path}: {e}")
            return

        for name in sorted(entries):
            if name.startswith("."):
                continue
            full_path = os.path.join(path, name)
            if os.path.isdir(full_path):
                dir_item = QtWidgets.QTreeWidgetItem([name, "Directory"])
                dir_item.full_path = full_path
                if parent_item:
                    parent_item.addChild(dir_item)
                else:
                    self.tree.addTopLevelItem(dir_item)
            elif name.lower().endswith(".scad"):
                file_item = QtWidgets.QTreeWidgetItem([name, "SCAD File"])
                file_item.full_path = full_path
                if parent_item:
                    parent_item.addChild(file_item)
                else:
                    self.tree.addTopLevelItem(file_item)

    def on_item_clicked(self, item, column):
        self.selected_item = item
        if hasattr(item, "full_path"):
            full_path = item.full_path
            if os.path.isdir(full_path):
                item.takeChildren()
                self.populate_tree(path=full_path, parent_item=item)
                self.selected_dir = full_path
                self.selected_scad = None
                self.create_btn.setEnabled(False)
                self.edit_btn.setEnabled(False)
                self.scan_btn.setEnabled(False)
                self.status.setText(f"Selected directory: {full_path}")
            elif full_path.lower().endswith(".scad"):
                self.selected_scad = full_path
                self.selected_dir = None
                self.create_btn.setEnabled(True)
                self.edit_btn.setEnabled(True)
                self.scan_btn.setEnabled(True)
                self.status.setText(f"Selected SCAD file: {full_path}")

    def create_scad_object(self):
        if not self.selected_scad:
            return

        # Capture required values BEFORE closing
        selected_scad = self.selected_scad

        # Close dialog first
        self.accept()   # preferred over close() for dialogs

        # Defer creation until dialog is gone
        QtCore.QTimer.singleShot(
            0,
            lambda: self._create_scad_object_impl(selected_scad)
            )

    def _create_scad_object_impl(self, selected_scad):

        import os
        write_log("Info",f"Create SCAD Object {self.selected_scad}")
        if not self.selected_scad:
            return

        #sourceDirectory = BaseParams.getScadSourcePath()
        baseName = os.path.basename(self.selected_scad)
        write_log("Info",f"baseName {baseName}")
        objectName = baseName.split('.')[0]
        write_log("Indo",f"Object Name {objectName}")
        #scadSourceFile = os.path.join(sourceDirectory,baseName)
        createOption = True
        
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument(objectName)

        title = f"Create SCAD Object {objectName}"
        #title, createOption, objectName, filename
        #createSCADObject(title, createOption, objectName, scadSourceFile)
        createSCADObject(title, createOption, objectName, self.selected_scad)
        
        doc.recompute()

        self.status.setText(f"Created SCAD Object: {objectName}")
        write_log("Info", f"Created SCAD Object: {objectName}")

    def edit_copy(self):
        if not self.selected_scad:
            return

        write_log("Info", f"Editing copy of {self.selected_scad}")
        obj_name = os.path.splitext(os.path.basename(self.selected_scad))[0]
        bp = BaseParams()
        bp.editFile(obj_name, self.selected_scad)
        self.status.setText(f"Opened SCAD file for editing: {self.selected_scad}")

    def scan_modules(self):
        if not self.selected_scad or not os.path.isfile(self.selected_scad):
            QtWidgets.QMessageBox.warning(self, "Scan Modules", "No SCAD file selected.")
            return

        write_log("Info", f"Scanning SCAD file: {self.selected_scad}")

        try:
            meta = parse_scad_for_modules(self.selected_scad)
            if not meta.modules:
                QtWidgets.QMessageBox.information(self, "Scan Modules", "No documented modules found.")
                write_log("Info", "No modules found in SCAD file.")
                return

            dialog = SCAD_Module_Dialog(meta, parent=self)
            #dialog = SCAD_Module_Dialog(parent=self, module=mod, meta=meta)
            dialog.exec_()
            write_log("Info", "ModuleSCAD dialog executed.")

        except Exception as e:
            write_log("Error", f"Module scan failed: {e}")
            QtWidgets.QMessageBox.critical(self, "Scan Modules", f"Error scanning modules:\n{e}")

