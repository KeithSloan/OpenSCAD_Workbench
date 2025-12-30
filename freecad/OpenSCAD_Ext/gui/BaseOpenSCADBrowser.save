import os
from PySide import QtCore, QtGui, QtWidgets

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log


class BaseOpenSCADBrowser(QtWidgets.QDialog):
    """
    Base class for OpenSCAD library browsers.

    Responsibilities:
    - Provide dialog shell
    - Display SCAD meta in a tree
    - Handle selection and notify subclasses

    IMPORTANT:
    - This class does NOT scan the filesystem.
    - Caller must call populate_from_meta_list(meta_list).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("OpenSCAD Library")
        self.setMinimumSize(700, 500)

        self.scad_entries = []
        self.selected_meta = None

        # Build UI (implemented by subclass)
        self.setupUI()

        # Connect signals
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI hooks
    # ------------------------------------------------------------------

    def setupUI(self):
        """
        Must be implemented by subclass.
        Must create self.tree (QTreeWidget).
        """
        raise NotImplementedError

    def _connect_signals(self):
        if hasattr(self, "tree"):
            self.tree.itemSelectionChanged.connect(
                self._on_selection_changed
            )

    # ------------------------------------------------------------------
    # Data population (EXPLICIT)
    # ------------------------------------------------------------------

    def populate_from_meta_list(self, meta_list):
        """
        Populate tree from a list of SCAD meta dicts.

        meta = {
            "path": ".../file.scad",
            "modules": {...},
            "functions": {...}
        }
        """
        self.tree.clear()
        self.scad_entries = meta_list or []

        for meta in self.scad_entries:
            path = meta.get("path")
            if not path:
                continue

            name = os.path.basename(path)
            item = QtWidgets.QTreeWidgetItem([name, "SCAD"])
            item.meta = meta
            self.tree.addTopLevelItem(item)

        write_log("Info", f"Displayed {len(self.scad_entries)} SCAD files")

    # ------------------------------------------------------------------
    # Selection handling
    # ------------------------------------------------------------------

    def _on_selection_changed(self):
        items = self.tree.selectedItems()
        if not items:
            self._set_selection(None)
            return

        item = items[0]
        meta = getattr(item, "meta", None)
        self._set_selection(meta)

    def _set_selection(self, meta):
        self.selected_meta = meta

        if hasattr(self, "set_selected_meta"):
            self.set_selected_meta(meta)
        elif hasattr(self, "update_buttons"):
            self.update_buttons(bool(meta))

        if meta:
            write_log("Info", f"Selected SCAD: {meta.get('path')}")
        else:
            write_log("Info", "Selection cleared")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def clear_selection(self):
        self.tree.clearSelection()
        self._set_selection(None)

