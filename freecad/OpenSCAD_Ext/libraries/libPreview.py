class OpenSCADLibraryBrowserWithPreview(BaseOpenSCADBrowser):
    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Splitter for tree + preview
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter)

        # Tree view
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Type"])
        self.tree.itemClicked.connect(self.on_item_selected)
        self.tree.itemDoubleClicked.connect(self.on_item_selected)
        splitter.addWidget(self.tree)

        # Preview pane
        self.preview = QtWidgets.QTextEdit()
        self.preview.setReadOnly(True)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(1, 1)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_create = QtWidgets.QPushButton("Create SCAD Object")
        self.btn_create.clicked.connect(self.create_scad_object)
        self.btn_create.setEnabled(False)
        btn_layout.addWidget(self.btn_create)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Status
        self.status = QtWidgets.QLabel("")
        layout.addWidget(self.status)

    def update_preview(self, path):
        if path and os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    lines = "".join([next(f) for _ in range(20)])
                self.preview.setPlainText(lines)
            except Exception:
                self.preview.setPlainText("(Unable to load preview)")
        else:
            self.preview.setPlainText("")

