import os
from pathlib import Path
import FreeCAD
from PySide import QtWidgets

from freecad.OpenSCAD_Ext.libraries.ensure_openSCADPATH import ensure_openSCADPATH
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.core.create_scad_object_interactive import create_scad_object_interactive

# New Lark-based scanner – single import for all metadata needs
from freecad.OpenSCAD_Ext.parsers.scadmeta import scan_scad_file, ScadFileType
from freecad.OpenSCAD_Ext.gui.SCAD_Module_Dialog import SCAD_Module_Dialog


# ---------------------------------------------------------------------------
# File-type label helpers
# ---------------------------------------------------------------------------

_FILE_TYPE_LABELS = {
    ScadFileType.PURE_SCAD:      "Pure SCAD",
    ScadFileType.LIBRARY:        "Library",
    ScadFileType.VARIABLE:       "Variables",
    ScadFileType.MODULES_ONLY:   "Modules",
    ScadFileType.FUNCTIONS_ONLY: "Functions",
    ScadFileType.MIXED:          "Mixed",
    ScadFileType.UNKNOWN:        "SCAD File",
}

_FILE_TYPE_TIPS = {
    ScadFileType.PURE_SCAD:      "Produces geometry when run directly",
    ScadFileType.LIBRARY:        "Include/use aggregator — no own definitions",
    ScadFileType.VARIABLE:       "Only variable definitions",
    ScadFileType.MODULES_ONLY:   "Module definitions",
    ScadFileType.FUNCTIONS_ONLY: "Function definitions",
    ScadFileType.MIXED:          "Module and function definitions",
    ScadFileType.UNKNOWN:        "Empty or unclassified",
}


class OpenSCADLibraryBrowser(QtWidgets.QDialog):
    """
    OpenSCAD Library Browser dialog.
    Displays directories and SCAD files in OPENSCADPATH, annotated with
    the scadmeta file-type classification.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OpenSCAD Library Browser")
        self.resize(750, 520)
        self.selected_item = None
        self.selected_scad = None
        self.selected_dir = None
        self._meta_cache: dict = {}   # path -> ScadMeta (session-level cache)

        self.setupUI()
        self.populate_tree()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Tree – three columns: Name | Type | Modules | Functions
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Name", "File Type", "Mods", "Fns"])
        self.tree.setColumnWidth(0, 420)
        self.tree.setColumnWidth(1, 120)
        self.tree.setColumnWidth(2, 45)
        self.tree.setColumnWidth(3, 45)
        self.tree.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.tree)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()

        self.create_btn = QtWidgets.QPushButton("Create SCAD Object")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self.create_scad_object_action)

        self.extract_btn = QtWidgets.QPushButton("Extract Variables")
        self.extract_btn.setEnabled(False)
        self.extract_btn.clicked.connect(self.extract_variables)

        self.scan_btn = QtWidgets.QPushButton("Scan Modules")
        self.scan_btn.setEnabled(False)
        self.scan_btn.clicked.connect(self.scan_modules)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.close)

        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(self.extract_btn)
        btn_layout.addWidget(self.scan_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # Status bar
        self.status = QtWidgets.QLabel("")
        layout.addWidget(self.status)

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

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
                item = QtWidgets.QTreeWidgetItem([name, "Directory", "", ""])
                item.full_path = full_path
                _add_to_tree(self.tree, parent_item, item)

            elif name.lower().endswith(".scad"):
                # Fast scan for type label (uses cache)
                meta = self._get_meta(full_path)
                type_label = _FILE_TYPE_LABELS.get(meta.file_type, "SCAD File")
                mod_count = str(meta.module_count) if meta.module_count else ""
                fn_count  = str(meta.function_count) if meta.function_count else ""

                item = QtWidgets.QTreeWidgetItem([name, type_label, mod_count, fn_count])
                item.setToolTip(1, _FILE_TYPE_TIPS.get(meta.file_type, ""))
                item.full_path = full_path
                _add_to_tree(self.tree, parent_item, item)

    def _get_meta(self, path: str):
        """Return cached ScadMeta for *path*, scanning if needed."""
        if path not in self._meta_cache:
            self._meta_cache[path] = scan_scad_file(path)
        return self._meta_cache[path]

    # ------------------------------------------------------------------
    # Item click
    # ------------------------------------------------------------------

    def on_item_clicked(self, item, column):
        self.selected_item = item
        if not hasattr(item, "full_path"):
            return

        full_path = item.full_path

        if os.path.isdir(full_path):
            item.takeChildren()
            self.populate_tree(path=full_path, parent_item=item)
            self.selected_dir = full_path
            self.selected_scad = None
            self.create_btn.setEnabled(False)
            self.extract_btn.setEnabled(False)
            self.scan_btn.setEnabled(False)
            self.status.setText(f"Directory: {full_path}")

        elif full_path.lower().endswith(".scad"):
            self.selected_scad = full_path
            self.selected_dir = None
            meta = self._get_meta(full_path)
            has_modules   = meta.module_count > 0
            has_variables = len(meta.variables) > 0
            self.create_btn.setEnabled(True)
            self.extract_btn.setEnabled(has_variables)
            self.scan_btn.setEnabled(has_modules)
            self.status.setText(
                f"{os.path.basename(full_path)}  "
                f"[{_FILE_TYPE_LABELS.get(meta.file_type, '?')}]  "
                f"modules={meta.module_count}  "
                f"functions={meta.function_count}  "
                f"vars={len(meta.variables)}"
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def create_scad_object_action(self):
        if not self.selected_scad:
            return
        write_log("Info", f"Create SCAD Object {self.selected_scad}")
        scad_name = Path(self.selected_scad).stem
        create_scad_object_interactive(
            "Create SCAD Object",
            newFile=False,
            scadName=scad_name,
            sourceFile=self.selected_scad,
        )

    def extract_variables(self):
        if not self.selected_scad:
            return

        write_log("Info", f"Extracting variables from {self.selected_scad}")
        meta = self._get_meta(self.selected_scad)

        if not meta.variables:
            QtWidgets.QMessageBox.information(
                self, "Extract Variables", "No top-level variables found."
            )
            return

        doc = FreeCAD.ActiveDocument
        if not doc:
            self.status.setText("No active document — open or create one first.")
            return

        # Build a spreadsheet from meta.variables
        sheet_name = Path(self.selected_scad).stem + "_Vars"
        sheet = doc.getObject(sheet_name)
        if sheet is None:
            sheet = doc.addObject("Spreadsheet::Sheet", sheet_name)
            sheet.Label = sheet_name

        sheet.set("A1", '="Name"')
        sheet.set("B1", '="Expression"')
        row = 2
        for var_name, expr in meta.variables.items():
            sheet.set(f"A{row}", f'="{var_name}"')
            sheet.set(f"B{row}", str(expr))
            row += 1

        doc.recompute()
        self.status.setText(
            f"Extracted {len(meta.variables)} variables → spreadsheet '{sheet_name}'"
        )
        write_log("Info", f"Variables spreadsheet '{sheet_name}' created.")

    def scan_modules(self):
        if not self.selected_scad or not os.path.isfile(self.selected_scad):
            QtWidgets.QMessageBox.warning(self, "Scan Modules", "No SCAD file selected.")
            return

        write_log("Info", f"Scanning modules in: {self.selected_scad}")

        try:
            meta = self._get_meta(self.selected_scad)

            if not meta.modules:
                QtWidgets.QMessageBox.information(
                    self, "Scan Modules", "No modules found in this file."
                )
                write_log("Info", "No modules found.")
                return

            dialog = SCAD_Module_Dialog(meta, parent=self)
            dialog.exec_()
            write_log("Info", "SCAD_Module_Dialog closed.")

        except Exception as e:
            write_log("Error", f"Module scan failed: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Scan Modules", f"Error scanning modules:\n{e}"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_to_tree(tree: QtWidgets.QTreeWidget, parent, item):
    if parent:
        parent.addChild(item)
    else:
        tree.addTopLevelItem(item)
