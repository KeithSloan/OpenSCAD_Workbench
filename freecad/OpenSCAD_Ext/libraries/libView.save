from PySide import QtCore, QtGui, QtWidgets
from freecad.OpenSCAD_Ext.libraries.baseLib import BaseOpenSCADBrowser
from freecad.OpenSCAD_Ext.commands import baseSCAD


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

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.close)

        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        # Status
        self.status = QtWidgets.QLabel("")
        layout.addWidget(self.status)

    def edit_copy(self):
        if not self.selected_scad:
            return

        baseSCAD.editCopy(self.selected_scad)
        self.status.setText("Opened SCAD file for editing (copy)")

