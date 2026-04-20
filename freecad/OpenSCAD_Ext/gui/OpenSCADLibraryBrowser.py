import os
from pathlib import Path
import FreeCAD
import FreeCADGui
from PySide import QtWidgets
from PySide.QtCore import QSize
from PySide.QtGui import QBrush, QColor

from freecad.OpenSCAD_Ext.libraries.ensure_openSCADPATH import ensure_openSCADPATH
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.core.create_scad_object import create_scad_object
from freecad.OpenSCAD_Ext.core.exporters import export_variables
from freecad.OpenSCAD_Ext.core.varset_utils import create_module_varsets, create_toplevel_varset
from freecad.OpenSCAD_Ext.gui.OpenSCADeditOptions import OpenSCADeditOptions

# Lark-based scanner – single import for all metadata needs
from freecad.OpenSCAD_Ext.parsers.scadmeta import scan_scad_file, ScadFileType
from freecad.OpenSCAD_Ext.gui.SCAD_Module_Dialog import SCAD_Module_Dialog

# Display helpers: labels, colours, icons
from freecad.OpenSCAD_Ext.gui.scad_type_display import (
    FILE_TYPE_LABELS,
    FILE_TYPE_TIPS,
    DIR_COLOUR,
    get_file_type_icon,
    get_dir_icon,
    get_file_type_color,
)


# ---------------------------------------------------------------------------
# Variable preview dialog
# ---------------------------------------------------------------------------

class _VarPreviewDialog(QtWidgets.QDialog):
    """Show variables found in a SCAD file before creating an object."""

    def __init__(self, meta, parent=None):
        super().__init__(parent)
        self.setWindowTitle("File Variables — Customizer Parameters")
        self.resize(520, 300)
        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(QtWidgets.QLabel(
            f"<b>{len(meta.variables)}</b> parameter variable(s) found — "
            "a VarSet will be created automatically."
        ))

        table = QtWidgets.QTableWidget(len(meta.variables), 3)
        table.setHorizontalHeaderLabels(["Name", "Default", "Description"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)

        for row, (name, expr) in enumerate(meta.variables.items()):
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(expr))
            desc = meta.variable_descriptions.get(name, "")
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(desc))

        table.resizeColumnToContents(0)
        table.resizeColumnToContents(1)
        layout.addWidget(table)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)


# ---------------------------------------------------------------------------
# Main browser dialog
# ---------------------------------------------------------------------------

class OpenSCADLibraryBrowser(QtWidgets.QDialog):
    """
    OpenSCAD Library Browser dialog.

    Displays directories and SCAD files found on OPENSCADPATH, annotated with
    the scadmeta file-type classification.  Each SCAD file is scanned for
    metadata (modules, functions, variables) using the Lark-based scanner.

    Caching strategy
    ----------------
    A session-level dict ``_meta_cache`` stores ``(mtime, ScadMeta)`` pairs so
    that repeated accesses within one dialog session are cheap.  Before
    returning a cached result the file's mtime is compared.  If it has changed
    the session entry is discarded and ``scan_scad_file()`` is called again,
    which in turn validates against the TinyDB persistent cache via SHA-256 and
    re-parses only when the content has actually changed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OpenSCAD Library Browser")
        self.resize(820, 560)
        self.selected_item = None
        self.selected_scad = None
        self.selected_dir = None

        # session cache: path -> (mtime: float, meta: ScadMeta)
        self._meta_cache: dict = {}
        self._root_path = None

        self._setup_ui()
        self._populate_tree()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Navigation row: Up button + breadcrumb path label
        nav_layout = QtWidgets.QHBoxLayout()
        self.up_btn = QtWidgets.QPushButton("▲ Up")
        self.up_btn.setFixedWidth(60)
        self.up_btn.setToolTip("Navigate to parent directory")
        self.up_btn.setEnabled(False)
        self.up_btn.clicked.connect(self._navigate_up)
        self.path_label = QtWidgets.QLabel("")
        self.path_label.setStyleSheet("color: #555; font-size: 11px;")
        nav_layout.addWidget(self.up_btn)
        nav_layout.addWidget(self.path_label, 1)
        layout.addLayout(nav_layout)

        # Tree – columns: Name | Type | Mods | Funcs | Vars
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Name", "File Type", "Mods", "Funcs", "Vars"])
        self.tree.setColumnWidth(0, 380)
        self.tree.setColumnWidth(1, 130)
        self.tree.setColumnWidth(2, 50)
        self.tree.setColumnWidth(3, 50)
        self.tree.setColumnWidth(4, 50)
        self.tree.setIconSize(QSize(16, 16))
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

        # Action buttons
        btn_layout = QtWidgets.QHBoxLayout()

        self.create_btn = QtWidgets.QPushButton("Create SCAD Object")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self._create_scad_object)

        self.extract_btn = QtWidgets.QPushButton("Extract Variables")
        self.extract_btn.setEnabled(False)
        self.extract_btn.clicked.connect(self._extract_variables)

        self.scan_btn = QtWidgets.QPushButton("Scan Modules")
        self.scan_btn.setEnabled(False)
        self.scan_btn.clicked.connect(self._scan_modules)

        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setToolTip("Force re-scan of the selected file, ignoring cached metadata")
        self.refresh_btn.clicked.connect(self._force_refresh)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.close)

        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(self.extract_btn)
        btn_layout.addWidget(self.scan_btn)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # Status / info bar
        self.status = QtWidgets.QLabel("")
        layout.addWidget(self.status)

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _populate_tree(self, path=None, parent_item=None):
        """Populate the tree starting at *path* (defaults to OPENSCADPATH root)."""
        if path is None:
            path = ensure_openSCADPATH()
            self._root_path = path
            self.path_label.setText(path)
            write_log("Info", f"Displaying SCAD library directory: {path}")

        try:
            entries = os.listdir(path)
        except Exception as exc:
            write_log("Error", f"Cannot list folder {path}: {exc}")
            return

        dir_icon = get_dir_icon()

        for name in sorted(entries):
            if name.startswith("."):
                continue
            full_path = os.path.join(path, name)

            if os.path.isdir(full_path):
                item = QtWidgets.QTreeWidgetItem([name, "Directory", "", "", ""])
                if dir_icon:
                    item.setIcon(0, dir_icon)
                item.setForeground(1, QBrush(QColor(DIR_COLOUR)))
                item.full_path = full_path
                _add_to_tree(self.tree, parent_item, item)

            elif name.lower().endswith(".scad"):
                item = self._make_scad_item(name, full_path)
                _add_to_tree(self.tree, parent_item, item)

    def _make_scad_item(self, name: str, full_path: str) -> QtWidgets.QTreeWidgetItem:
        """Build a decorated tree item for a single SCAD file."""
        meta = self._get_meta(full_path)
        label = FILE_TYPE_LABELS.get(meta.file_type, "SCAD File")
        tip   = FILE_TYPE_TIPS.get(meta.file_type, "")
        icon  = get_file_type_icon(meta.file_type)
        color = get_file_type_color(meta.file_type)

        mod_count = str(meta.module_count)   if meta.module_count   else ""
        fn_count  = str(meta.function_count) if meta.function_count else ""
        var_count = str(len(meta.variables)) if meta.variables      else ""

        item = QtWidgets.QTreeWidgetItem([name, label, mod_count, fn_count, var_count])
        if icon:
            item.setIcon(1, icon)
        if color:
            item.setForeground(1, QBrush(color))
        item.setToolTip(1, tip)
        item.full_path = full_path
        return item

    def _refresh_item_display(self, item: QtWidgets.QTreeWidgetItem, full_path: str):
        """Refresh the visual state of a tree row after a re-scan."""
        meta  = self._get_meta(full_path)
        label = FILE_TYPE_LABELS.get(meta.file_type, "SCAD File")
        tip   = FILE_TYPE_TIPS.get(meta.file_type, "")
        icon  = get_file_type_icon(meta.file_type)
        color = get_file_type_color(meta.file_type)

        item.setText(1, label)
        item.setText(2, str(meta.module_count)   if meta.module_count   else "")
        item.setText(3, str(meta.function_count) if meta.function_count else "")
        item.setText(4, str(len(meta.variables)) if meta.variables      else "")
        if icon:
            item.setIcon(1, icon)
        if color:
            item.setForeground(1, QBrush(color))
        item.setToolTip(1, tip)

    # ------------------------------------------------------------------
    # Session-level metadata cache (mtime-aware)
    # ------------------------------------------------------------------

    def _get_meta(self, path: str):
        """
        Return a :class:`~parsers.scadmeta.ScadMeta` for *path*.

        Uses a session-level dict keyed by ``path`` storing
        ``(mtime, ScadMeta)`` pairs.

        * Re-clicking an unchanged file → dict lookup only (free).
        * File modified while browser is open → session entry discarded,
          ``scan_scad_file()`` called (which validates TinyDB via hash).
        """
        try:
            current_mtime = os.path.getmtime(path)
        except OSError:
            current_mtime = 0.0

        cached = self._meta_cache.get(path)
        if cached is not None:
            cached_mtime, meta = cached
            if abs(current_mtime - cached_mtime) < 0.002:
                return meta  # file unchanged – return session-cached result
            # File modified since last session scan – discard and re-scan
            write_log("Info",
                f"[LibraryBrowser] file changed, invalidating session cache: "
                f"{os.path.basename(path)}")
            del self._meta_cache[path]

        # scan_scad_file() checks TinyDB (mtime then SHA-256) before parsing
        meta = scan_scad_file(path)
        self._meta_cache[path] = (current_mtime, meta)
        return meta

    def _invalidate_session_cache(self, path: str):
        """Remove *path* from the session cache so the next access re-scans."""
        self._meta_cache.pop(path, None)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate_up(self):
        """Navigate to the parent of the currently selected tree item."""
        current = self.tree.currentItem()
        if current is None:
            return
        parent = current.parent()
        if parent is not None:
            self.tree.setCurrentItem(parent)
            self._on_item_clicked(parent, 0)
        else:
            # Current item is a top-level directory — go back to root view
            self.tree.clearSelection()
            self.up_btn.setEnabled(False)
            self.path_label.setText(self._root_path or "")
            self.selected_dir = None
            self.selected_scad = None
            self.create_btn.setEnabled(False)
            self.extract_btn.setEnabled(False)
            self.scan_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.status.setText("")

    # ------------------------------------------------------------------
    # Item click handler
    # ------------------------------------------------------------------

    def _on_item_clicked(self, item, column):
        self.selected_item = item
        if not hasattr(item, "full_path"):
            return

        full_path = item.full_path

        # Enable Up button whenever the selected path is not the root
        self.up_btn.setEnabled(full_path != self._root_path)
        self.path_label.setText(full_path)

        if os.path.isdir(full_path):
            item.takeChildren()
            self._populate_tree(path=full_path, parent_item=item)
            self.selected_dir = full_path
            self.selected_scad = None
            self.create_btn.setEnabled(False)
            self.extract_btn.setEnabled(False)
            self.scan_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.status.setText(f"Directory: {full_path}")

        elif full_path.lower().endswith(".scad"):
            self.selected_scad = full_path
            self.selected_dir = None

            meta = self._get_meta(full_path)
            has_modules   = meta.module_count > 0
            has_variables = bool(meta.variables)

            self.create_btn.setEnabled(True)
            self.extract_btn.setEnabled(has_modules or has_variables)
            self.scan_btn.setEnabled(has_modules)
            self.refresh_btn.setEnabled(True)

            label = FILE_TYPE_LABELS.get(meta.file_type, "?")
            self.status.setText(
                f"{os.path.basename(full_path)}  "
                f"[{label}]  "
                f"mods={meta.module_count}  "
                f"funcs={meta.function_count}  "
                f"vars={len(meta.variables)}"
            )

    # ------------------------------------------------------------------
    # Button actions
    # ------------------------------------------------------------------

    def _create_scad_object(self):
        if not self.selected_scad:
            return

        meta = self._get_meta(self.selected_scad)
        has_variables = bool(meta.variables)

        # Show variable preview if file has customizer-style variables
        if has_variables:
            preview = _VarPreviewDialog(meta, parent=self)
            if preview.exec_() != QtWidgets.QDialog.Accepted:
                return

        write_log("Info", f"Create SCAD Object: {self.selected_scad}")

        dlg = OpenSCADeditOptions(
            "Create SCAD Object",
            newFile=False,
            scadName=Path(self.selected_scad).stem,
            sourceFile=self.selected_scad,
        )
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        params = dlg.getValues()
        if not params.get("scadName"):
            return

        obj = create_scad_object(
            scadName=params["scadName"],
            geometryType=params["geometryType"],
            fnMax=params["fnMax"],
            timeOut=params["timeOut"],
            keepOption=params["keepOption"],
            newFile=params["newFile"],
            sourceFile=params["sourceFile"],
        )

        if obj is not None:
            # Auto-create VarSet and link it to the SCAD object
            if has_variables:
                doc = FreeCAD.ActiveDocument
                if doc:
                    stem = Path(self.selected_scad).stem
                    varset_name = f"{stem}_Vars"
                    varset = create_toplevel_varset(doc, meta, varset_name)
                    if varset is not None and hasattr(obj, 'linked_varset'):
                        obj.linked_varset = varset
                        write_log("Info",
                            f"Linked VarSet '{varset.Name}' → SCAD object '{obj.Name}'")
                    doc.recompute()

            self.status.setText(
                f"Created: {params['scadName']}"
                + (" + VarSet (linked)" if has_variables else "")
            )

            if params.get("closeAfter", True):
                self.close()

    def _extract_variables(self):
        if not self.selected_scad:
            return

        write_log("Info", f"Extracting variables from {self.selected_scad}")
        meta = self._get_meta(self.selected_scad)

        label = Path(self.selected_scad).stem

        doc = FreeCAD.ActiveDocument
        if not doc:
            doc_name = label.replace("_", "-")
            doc = FreeCAD.newDocument(doc_name)
            write_log("Info", f"Created new document '{doc_name}'")

        n_modules = create_module_varsets(doc, meta)
        toplevel_varset = create_toplevel_varset(doc, meta, label)
        doc.recompute()

        parts = []
        if n_modules:
            parts.append(f"{n_modules} module VarSet(s)")
        if toplevel_varset is not None:
            parts.append(f"top-level VarSet '{toplevel_varset.Label}'")
        if parts:
            self.status.setText(f"Extracted from '{label}': " + ", ".join(parts))
        else:
            self.status.setText(f"Nothing to extract from '{label}'")

    def _scan_modules(self):
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
                return

            dialog = SCAD_Module_Dialog(meta, parent=self)
            dialog.exec_()
            write_log("Info", "SCAD_Module_Dialog closed.")

        except Exception as exc:
            write_log("Error", f"Module scan failed: {exc}")
            QtWidgets.QMessageBox.critical(
                self, "Scan Modules", f"Error scanning modules:\n{exc}"
            )

    def _force_refresh(self):
        """Discard all caches for the selected file and re-scan it."""
        if not self.selected_scad:
            return

        path = self.selected_scad
        write_log("Info", f"[LibraryBrowser] force refresh: {path}")

        # Drop session cache entry
        self._invalidate_session_cache(path)

        # Drop TinyDB persistent cache entry
        try:
            from freecad.OpenSCAD_Ext.parsers.scadmeta import get_cache
            get_cache().invalidate(path)
        except Exception:
            pass

        # Re-scan (bypasses both caches)
        from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_scanner import scan_scad_file as _scan
        meta = _scan(path, use_cache=False)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0.0
        self._meta_cache[path] = (mtime, meta)

        # Refresh the tree row
        if self.selected_item and hasattr(self.selected_item, "full_path"):
            self._refresh_item_display(self.selected_item, path)

        label = FILE_TYPE_LABELS.get(meta.file_type, "?")
        self.status.setText(
            f"{os.path.basename(path)}  [{label}]  "
            f"mods={meta.module_count}  "
            f"funcs={meta.function_count}  "
            f"vars={len(meta.variables)}  (re-scanned)"
        )

        # Update button states after refresh
        self.extract_btn.setEnabled(meta.module_count > 0 or bool(meta.variables))
        self.scan_btn.setEnabled(meta.module_count > 0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_to_tree(tree: QtWidgets.QTreeWidget, parent, item):
    if parent:
        parent.addChild(item)
    else:
        tree.addTopLevelItem(item)
