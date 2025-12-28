from PySide2 import QtWidgets, QtCore


class SCAD_Module_Dialog(QtWidgets.QDialog):
    """
    Dialog to browse a SCAD library and select a module + parameters.
    Returns data only. No FreeCAD object creation here.
    """

    def __init__(self, scad_library, parent=None):
        super().__init__(parent)

        self.scad_library = scad_library
        self.selected_module = None
        self.arg_widgets = {}

        self.setWindowTitle(f"SCAD Library – {scad_library.filename}")
        self.resize(900, 600)

        self._build_ui()
        self._populate_library_info()
        self._populate_modules()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        # ---------- Library header ----------
        self.lib_info = QtWidgets.QLabel()
        self.lib_info.setWordWrap(True)
        self.lib_info.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(self.lib_info)

        self.includes_box = QtWidgets.QTextEdit()
        self.includes_box.setReadOnly(True)
        self.includes_box.setMaximumHeight(80)
        main_layout.addWidget(self.includes_box)

        # ---------- Splitter ----------
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # ---------- Module list ----------
        self.module_list = QtWidgets.QListWidget()
        self.module_list.currentItemChanged.connect(
            self._on_module_selected
        )
        splitter.addWidget(self.module_list)

        # ---------- Right panel ----------
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)

        # ---------- Module documentation ----------
        self.module_doc = QtWidgets.QTextEdit()
        self.module_doc.setReadOnly(True)
        right_layout.addWidget(self.module_doc)

        # ---------- Arguments editor ----------
        args_group = QtWidgets.QGroupBox("Module Arguments")
        args_layout = QtWidgets.QVBoxLayout(args_group)

        self.args_scroll = QtWidgets.QScrollArea()
        self.args_scroll.setWidgetResizable(True)

        self.args_widget = QtWidgets.QWidget()
        self.args_form = QtWidgets.QFormLayout(self.args_widget)
        self.args_scroll.setWidget(self.args_widget)

        args_layout.addWidget(self.args_scroll)
        right_layout.addWidget(args_group, 1)

        # ---------- Buttons ----------
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        self.create_btn = QtWidgets.QPushButton("Create Object")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self.accept)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(cancel_btn)

        main_layout.addLayout(btn_layout)

        splitter.setStretchFactor(1, 1)

    # ------------------------------------------------------------------
    # Populate data
    # ------------------------------------------------------------------

    def _populate_library_info(self):
        self.lib_info.setText(
            f"{self.scad_library.filename}\n"
            f"{self.scad_library.summary}"
        )

        if self.scad_library.includes:
            self.includes_box.setPlainText(
                "Includes:\n" + "\n".join(self.scad_library.includes)
            )
        else:
            self.includes_box.setPlainText("Includes: none")

    def _populate_modules(self):
        self.module_list.clear()
        for mod in self.scad_library.modules:
            item = QtWidgets.QListWidgetItem(mod.name)
            item.setData(QtCore.Qt.UserRole, mod)
            self.module_list.addItem(item)

    # ------------------------------------------------------------------
    # Module selection
    # ------------------------------------------------------------------

    def _on_module_selected(self, item):
        if not item:
            self.create_btn.setEnabled(False)
            return

        module = item.data(QtCore.Qt.UserRole)
        self.selected_module = module
        self.create_btn.setEnabled(True)

        self._update_module_doc(module)
        self._build_argument_widgets(module)

    def _update_module_doc(self, module):
        parts = []

        if module.synopsis:
            parts.append(f"<b>Synopsis</b><br>{module.synopsis}<br><br>")

        if module.usage:
            parts.append(
                "<b>Usage</b><br>"
                f"<pre>{module.usage}</pre>"
            )

        if module.description:
            parts.append(
                f"<b>Description</b><br>{module.description}<br><br>"
            )

        self.module_doc.setHtml("".join(parts))

    # ------------------------------------------------------------------
    # Arguments editor
    # ------------------------------------------------------------------

    def _clear_arguments(self):
        while self.args_form.rowCount():
            self.args_form.removeRow(0)
        self.arg_widgets.clear()

    def _build_argument_widgets(self, module):
        self._clear_arguments()

        for arg in module.arguments:
            label = QtWidgets.QLabel(arg.name)
            label.setToolTip(arg.description or "")

            widget = self._create_arg_widget(arg)
            self.args_form.addRow(label, widget)

            self.arg_widgets[arg.name] = widget

    def _create_arg_widget(self, arg):
        default = arg.default

        # Boolean
        if default in ("true", "false"):
            cb = QtWidgets.QCheckBox()
            cb.setChecked(default == "true")
            return cb

        # Numeric
        if default is not None:
            try:
                val = float(default)
                sb = QtWidgets.QDoubleSpinBox()
                sb.setDecimals(4)
                sb.setRange(-1e9, 1e9)
                sb.setValue(val)
                return sb
            except Exception:
                pass

        # Fallback: string / enum
        le = QtWidgets.QLineEdit()
        if default:
            le.setText(str(default).strip('"'))
        return le

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_selected_module(self):
        return self.selected_module

    def get_argument_values(self):
        values = {}
        for name, widget in self.arg_widgets.items():
            if isinstance(widget, QtWidgets.QCheckBox):
                values[name] = widget.isChecked()
            elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                values[name] = widget.value()
            elif isinstance(widget, QtWidgets.QLineEdit):
                values[name] = widget.text()
        return values

