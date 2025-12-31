import re
from PySide2 import QtWidgets, QtCore
import FreeCAD
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.objects.SCADModuleObject import SCADModuleObject
from freecad.OpenSCAD_Ext.objects.SCADObject import ViewSCADProvider

class SCAD_Module_Dialog(QtWidgets.QDialog):
    """
    Display modules found in a SCAD file using meta.
    User selects a module, edits arguments, and creates a SCADModuleObject.
    """

    def __init__(self, meta, parent=None):
        super().__init__(parent)
        self.meta = meta
        self.selected_module_meta = None
        self.arg_widgets = {}

        self.setWindowTitle(f"SCAD Modules – {meta.sourceFile}")
        self.resize(1000, 600)

        self._build_ui()
        self._populate_includes()
        self._populate_modules()

    def _build_ui(self):
    # ----- Top horizontal layout: Includes panels -----
        includes_layout = QtWidgets.QHBoxLayout()

        # Left: Includes box
        includes_left_panel = QtWidgets.QWidget()
        left_includes_layout = QtWidgets.QVBoxLayout(includes_left_panel)
        left_includes_layout.addWidget(QtWidgets.QLabel("Includes:"))
        self.includes_box = QtWidgets.QTextEdit()
        self.includes_box.setReadOnly(True)
        self.includes_box.setMaximumHeight(80)
        left_includes_layout.addWidget(self.includes_box)
        includes_layout.addWidget(includes_left_panel, stretch=3)

        # Right: Comment Includes
        includes_right_panel = QtWidgets.QWidget()
        right_includes_layout = QtWidgets.QVBoxLayout(includes_right_panel)
        right_includes_layout.addWidget(QtWidgets.QLabel("Comment Includes:"))
        self.comment_includes = QtWidgets.QListWidget()
        self.comment_includes.addItems(getattr(self.meta, "comment_includes", []))
        right_includes_layout.addWidget(self.comment_includes)
        includes_layout.addWidget(includes_right_panel, stretch=1)

        # ----- Module Details (list) -----
        module_details_layout = QtWidgets.QVBoxLayout()
        module_details_layout.addWidget(QtWidgets.QLabel("Modules:"))
        self.module_list = QtWidgets.QListWidget()
        self.module_list.currentItemChanged.connect(self._on_module_selected)
        module_details_layout.addWidget(self.module_list, stretch=1)
        module_details_panel = QtWidgets.QWidget()
        module_details_panel.setLayout(module_details_layout)

        # ----- Module Description -----
        self.module_doc = QtWidgets.QTextEdit()
        self.module_doc.setReadOnly(True)
        module_desc_layout = QtWidgets.QVBoxLayout()
        module_desc_layout.addWidget(QtWidgets.QLabel("Module Description:"))
        module_desc_layout.addWidget(self.module_doc, stretch=1)
        module_desc_panel = QtWidgets.QWidget()
        module_desc_panel.setLayout(module_desc_layout)
        # ----- Arguments -----
        args_layout = QtWidgets.QVBoxLayout()
        args_layout.addWidget(QtWidgets.QLabel("Module Arguments:"))
        self.args_scroll = QtWidgets.QScrollArea()
        self.args_scroll.setWidgetResizable(True)
        self.args_widget = QtWidgets.QWidget()
        self.args_form = QtWidgets.QFormLayout(self.args_widget)
        self.args_scroll.setWidget(self.args_widget)
        args_layout.addWidget(self.args_scroll, stretch=7)
        args_panel = QtWidgets.QWidget()
        args_panel.setLayout(args_layout)

        # ----- Buttons -----
        btn_layout = QtWidgets.QHBoxLayout()
        self.create_btn = QtWidgets.QPushButton("Create SCAD Module Object")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self.create_object_clicked)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(cancel_btn)

        # ----- Final vertical layout -----
        main_vlayout = QtWidgets.QVBoxLayout()
        main_vlayout.addLayout(includes_layout)       # Top includes panels
        main_vlayout.addWidget(module_details_panel)  # Module Details
        main_vlayout.addWidget(module_desc_panel)     # Module Description
        main_vlayout.addWidget(args_panel)            # Arguments
        main_vlayout.addLayout(btn_layout)            # Buttons at bottom
        self.setLayout(main_vlayout)

    # ------------------------------------------------------------------
    # Populate includes and modules
    # ------------------------------------------------------------------

    def _populate_includes(self):
        includes = self.meta.includes if hasattr(self.meta, "includes") else []
        self.includes_box.setPlainText("\n".join(includes) if includes else "None")

    def _populate_modules(self):
        self.module_list.clear()
        for mod in getattr(self.meta, "modules", []):
            name = self.clean_name(mod.name)
            item = QtWidgets.QListWidgetItem(f"{name} – {mod.synopsis}")
            item.setData(QtCore.Qt.UserRole, mod)
            self.module_list.addItem(item)

    # ------------------------------------------------------------------
    # Module selection
    # ------------------------------------------------------------------

    def _on_module_selected(self, item):
        if not item:
            self.create_btn.setEnabled(False)
            return

        self.selected_module_meta = item.data(QtCore.Qt.UserRole)
        self.create_btn.setEnabled(True)
        self._update_module_doc()
        self._build_argument_widgets()

    def _update_module_doc(self):
        mod = self.selected_module_meta
        parts = []
        if mod.synopsis:
            parts.append(f"<b>Synopsis</b>: {mod.synopsis}<br>")
        if mod.description:
            parts.append(f"<b>Description</b>: {mod.description}<br>")
        self.module_doc.setHtml("".join(parts))

    # ------------------------------------------------------------------
    # Arguments editor
    # ------------------------------------------------------------------

    def _clear_arguments(self):
        while self.args_form.rowCount():
            self.args_form.removeRow(0)
        self.arg_widgets.clear()

    def _build_argument_widgets(self):
        self._clear_arguments()
        mod = self.selected_module_meta
        for arg in getattr(mod, "arguments", []):
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
        # String fallback
        le = QtWidgets.QLineEdit()
        if default is not None:
            le.setText(str(default).strip('"'))
        return le

    # ------------------------------------------------------------------
    # Create SCAD Module Object
    # ------------------------------------------------------------------
    def create_object_clicked(self):
        try:
            if not self.create_module_object():
                return   # validation failed → keep dialog open

            self.accept()   # SUCCESS → close dialog
        except Exception as err:
            FreeCAD.Console.PrintError(f"Create failed: {err}\n")

    def create_module_object(self):
        if not self.selected_module_meta:
            return

        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("SCAD_Import")

        # Collect argument values
        args_values = {}
        for name, widget in self.arg_widgets.items():
            if isinstance(widget, QtWidgets.QCheckBox):
                args_values[name] = widget.isChecked()
            elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                args_values[name] = widget.value()
            elif isinstance(widget, QtWidgets.QLineEdit):
                args_values[name] = widget.text()

        # Create object in FreeCAD
        write_log("Info","Create SCAD Module Object")
        obj_name = self.clean_name(self.selected_module_meta.name)
        obj = doc.addObject("Part::FeaturePython", obj_name)
        obj.Label = obj_name

        # View provider (THIS IS REQUIRED - Before calling SCADModuleObject)
        write_log("Indo","Set ViewProvider")
        ViewSCADProvider(obj.ViewObject)

        # Wrap in SCADModuleObject Data Proxy
        proxy = SCADModuleObject(obj, self.meta, self.selected_module_meta, args=args_values)

        doc.recompute()
        FreeCAD.Console.PrintMessage(f"[Info] SCADModuleObject created: {obj_name}\n")
        return True

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def clean_name(self, name):
        """Remove parentheses and trailing whitespace from module name"""
        return re.sub(r"\s*\(.*\)$", "", name).strip()

