# gui/customizer_import_dialog.py
"""
Dialog shown when importASTCSG detects a SCAD file with customizer variables.

Asks the user whether to import as a live parametric object (SCADfileBase +
VarSet) or as static geometry (compile-once CSG, no live link).

Returns one of:
    "parametric"  — create SCADfileBase + VarSet
    "static"      — continue with normal CSG import
    None          — user cancelled
"""

import os
from PySide import QtWidgets
from PySide.QtCore import Qt


class CustomizerImportDialog(QtWidgets.QDialog):
    """
    Ask how to import a SCAD file that has customizer (top-level) variables.
    """

    def __init__(self, filename, meta, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SCAD Customizer Detected")
        self.resize(540, 340)
        self._choice = None

        layout = QtWidgets.QVBoxLayout(self)

        # --- Header ---
        basename = os.path.basename(filename)
        n = len({k: v for k, v in meta.variables.items() if not k.startswith("_")})
        header = QtWidgets.QLabel(
            f"<b>{basename}</b> has <b>{n}</b> customizer parameter(s).<br>"
            "How do you want to import this file?"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # --- Variable preview table ---
        table = QtWidgets.QTableWidget(n, 3)
        table.setHorizontalHeaderLabels(["Parameter", "Default", "Description"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setMaximumHeight(140)

        row = 0
        for name, expr in meta.variables.items():
            if name.startswith("_"):
                continue
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(expr))
            desc = meta.variable_descriptions.get(name, "")
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(desc))
            row += 1

        table.resizeColumnToContents(0)
        table.resizeColumnToContents(1)
        layout.addWidget(table)

        # --- Radio buttons ---
        self._parametric_rb = QtWidgets.QRadioButton(
            "Parametric object  (recommended)\n"
            "Creates a live SCAD object with a linked VarSet.  "
            "Change a variable and recompute to update the geometry."
        )
        self._parametric_rb.setChecked(True)

        self._static_rb = QtWidgets.QRadioButton(
            "Static geometry\n"
            "Compiles to CSG once using the current default values.  "
            "No live link to the source file."
        )

        group_box = QtWidgets.QGroupBox("Import mode")
        gb_layout = QtWidgets.QVBoxLayout(group_box)
        gb_layout.addWidget(self._parametric_rb)
        gb_layout.addWidget(self._static_rb)
        layout.addWidget(group_box)

        # --- Buttons ---
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_accept(self):
        self._choice = "parametric" if self._parametric_rb.isChecked() else "static"
        self.accept()

    @property
    def choice(self):
        """Return "parametric", "static", or None (cancelled)."""
        return self._choice


def ask_customizer_import_mode(filename, meta, parent=None):
    """
    Convenience function: show the dialog and return the user's choice.

    Returns "parametric", "static", or None if cancelled.
    """
    dlg = CustomizerImportDialog(filename, meta, parent=parent)
    if dlg.exec_() == QtWidgets.QDialog.Accepted:
        return dlg.choice
    return None
