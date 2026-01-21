import os
from pathlib import Path
import FreeCAD
from PySide import QtWidgets

from freecad.OpenSCAD_Ext.libraries.ensure_openSCADPATH import ensure_openSCADPATH
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
#from freecad.OpenSCAD_Ext.commands.newSCAD import OpenSCADeditOptions
#from freecad.OpenSCAD_Ext.objects.SCADObject import create_scad_object
from freecad.OpenSCAD_Ext.core.create_scad_object_interactive import create_scad_object_interactive


# parse_library_scad for dialog SCADLibraryBrowser - BSOL2 etc
from freecad.OpenSCAD_Ext.parsers.parse_library_scad  import parse_scad_meta

from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_parse_scad_file  import create_scad_vars_spreadsheet
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
        self.create_btn.clicked.connect(self.create_scad_object_action)

        self.edit_btn = QtWidgets.QPushButton("Edit Copy")
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self.edit_copy)

        self.edit_btn = QtWidgets.QPushButton("Extract Variables")
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self.extract_variables)

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

    def create_scad_object_action(self):
        write_log("Info",f"Create SCAD Object {self.selected_scad}")
        if not self.selected_scad:
            return
        scadName = Path(self.selected_scad).stem

        create_scad_object_interactive(
            "Create SCAD Object",
            newFile=False, 
            scadName=scadName,
            sourceFile= self.selected_scad,
        )

    """
    def create_scad_object(title, scadName, scadFile, newObject):
        QtGui.QGuiApplication.setOverrideCursor(QtGui.Qt.ArrowCursor)
        dialog = OpenSCADeditOptions(
            scadName=self.selected_scad,
            newObject=False,
            parent=self
            )
        result = dialog.exec_()
        QtGui.QGuiApplication.restoreOverrideCursor()
        if result != QtGui.QDialog.Accepted:
            pass
        write_log("Info",f"Action")
        options = dialog.getValues()
        write_log("Info",f"Options {options}") 

        # Create SCAD Object
        scadName = dialog.getName()
        sourceFile = dialog.get_sourceFile()
        scadObj = dialog.create_from_dialog(scadName)
        if scadObj:
            scadObj.editFile(sourceFile)
    """

    def edit_copy(self):
        if not self.selected_scad:
            return

        write_log("Info", f"Editing copy of {self.selected_scad}")
        obj_name = os.path.splitext(os.path.basename(self.selected_scad))[0]
        bp = BaseParams()
        bp.editFile(obj_name, self.selected_scad)
        self.status.setText(f"Opened SCAD file for editing: {self.selected_scad}")

    def extract_variables(self):
        if not self.selected_scad:
            return

        write_log("Info", f"Extracting Variables from {self.selected_scad}")
        obj_name = os.path.splitext(os.path.basename(self.selected_scad))[0]
        meta = parse_scad_meta(self.selected_scad)
        write_log("Info",meta)
        doc = FreeCAD.ActiveDocument
        if doc:
            create_scad_vars_spreadsheet(doc, meta, obj_name)
        
        self.status.setText(f"Extracted Variables from SCAD file  {self.selected_scad}")

     
    def scan_modules(self):
        if not self.selected_scad or not os.path.isfile(self.selected_scad):
            QtWidgets.QMessageBox.warning(self, "Scan Modules", "No SCAD file selected.")
            return

        write_log("Info", f"Scanning SCAD file: {self.selected_scad}")

        try:
            meta = parse_scad_meta(self.selected_scad)
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
