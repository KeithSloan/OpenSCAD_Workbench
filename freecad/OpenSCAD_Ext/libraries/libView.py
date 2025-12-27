import os
from PySide import QtCore, QtWidgets

from freecad.OpenSCAD_Ext.libraries.baseLib import BaseOpenSCADBrowser


class OpenSCADLibraryBrowser(BaseOpenSCADBrowser):
    """
    Concrete OpenSCAD library browser dialog.
    """
    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Type"])

        # Better handling of long paths
        header = self.tree.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)

        self.tree.setTextElideMode(QtCore.Qt.ElideMiddle)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        layout.addWidget(self.tree)

        self.status = QtWidgets.QLabel("Select a SCAD file")
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(30)
        layout.addWidget(self.status)

        button_layout = QtWidgets.QHBoxLayout()

        self.create_btn = QtWidgets.QPushButton("Create")
        self.close_btn = QtWidgets.QPushButton("Close")

        button_layout.addWidget(self.create_btn)
        button_layout.addStretch(1)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

        self.tree.itemSelectionChanged.connect(self.on_selection_changed)
        self.create_btn.clicked.connect(self.create_scad_object)
        self.close_btn.clicked.connect(self.close)

        # Larger default window size for deep library trees
        self.resize(900, 600)


    def on_selection_changed(self):
        items = self.tree.selectedItems()
        if not items:
            self.selected_scad = None
            self.status.setText("Select a SCAD file")
            return

        item = items[0]
        path = item.data(0, 0)

        if path and os.path.isfile(path) and path.lower().endswith(".scad"):
            self.selected_scad = path
            self.status.setText(os.path.basename(path))
        else:
            self.selected_scad = None
            self.status.setText("Select a SCAD file")

