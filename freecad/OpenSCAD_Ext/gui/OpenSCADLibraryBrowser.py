import os
from pathlib import Path
import FreeCAD
from PySide import QtWidgets
from PySide.QtCore import QSize
from PySide.QtGui import QBrush, QColor

from freecad.OpenSCAD_Ext.libraries.ensure_openSCADPATH import ensure_openSCADPATH
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.core.create_scad_object_interactive import create_scad_object_interactive
from freecad.OpenSCAD_Ext.core.exporters import export_variables

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
        self.resize(780, 540)
        self.selected_item = None
        self.selected_scad = None
        self.selected_dir = None

        # session cache: path -> (mtime: float, meta: ScadMeta)
        self._meta_cache: dict = {}

        self._setup_ui()
        self._populate_tree()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Tree – columns: Name | Type | Mods | Fns
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Name", "File Type", "Mods", "Fns"])
        self.tree.setColumnWidth(0, 400)
        self.tree.setColumnWidth(1, 130)
        self.tree.setColumnWidth(2, 50)
        self.tree.setColumnWidth(3, 50)
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
                item = QtWidgets.QTreeWidgetItem([name, "Directory", "", ""])
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

        item = QtWidgets.QTreeWidgetItem([name, label, mod_count, fn_count])
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
    # Item click handler
    # ------------------------------------------------------------------

    def _on_item_clicked(self, item, column):
        self.selected_item = item
        if not hasattr(item, "full_path"):
            return

        full_path = item.full_path

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
            self.extract_btn.setEnabled(has_variables)
            self.scan_btn.setEnabled(has_modules)
            self.refresh_btn.setEnabled(True)

            label = FILE_TYPE_LABELS.get(meta.file_type, "?")
            self.status.setText(
                f"{os.path.basename(full_path)}  "
                f"[{label}]  "
                f"modules={meta.module_count}  "
                f"functions={meta.function_count}  "
                f"variables={len(meta.variables)}"
            )

    # ------------------------------------------------------------------
    # Button actions
    # ------------------------------------------------------------------

    def _create_scad_object(self):
        if not self.selected_scad:
            return
        write_log("Info", f"Create SCAD Object: {self.selected_scad}")
        create_scad_object_interactive(
            "Create SCAD Object",
            newFile=False,
            scadName=Path(self.selected_scad).stem,
            sourceFile=self.selected_scad,
        )

    def _extract_variables(self):
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

        label = Path(self.selected_scad).stem
        export_variables(doc, meta, label)
        self.status.setText(
            f"Exported {len(meta.variables)} variable(s) from '{label}'"
        )

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
            f"modules={meta.module_count}  "
            f"functions={meta.function_count}  "
            f"variables={len(meta.variables)}  (re-scanned)"
        )

        # Update button states after refresh
        self.extract_btn.setEnabled(bool(meta.variables))
        self.scan_btn.setEnabled(meta.module_count > 0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_to_tree(tree: QtWidgets.QTreeWidget, parent, item):
    if parent:
        parent.addChild(item)
    else:
        tree.addTopLevelItem(item)


