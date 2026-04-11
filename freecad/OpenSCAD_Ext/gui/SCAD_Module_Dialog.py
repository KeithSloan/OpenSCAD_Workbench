import os
import FreeCAD
from PySide import QtWidgets, QtCore

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.objects.SCADModuleObject import (
    SCADModuleObject,
    ViewSCADProvider,
)


def _finalize_meta_imports(meta, output_scad_path):
    """
    Resolve SCAD import strategy and store it on *meta*.

    Sets:
        meta.importStyle  -> "include" | "use"
        meta.importPaths  -> list of strings

    Works with the new :class:`~freecad.OpenSCAD_Ext.parsers.scadmeta.ScadMeta`
    (``source_file`` / ``base_name``) as well as the legacy ``SCADMeta``
    (``sourceFile`` / ``baseName``).
    """
    # Merge comment + normal includes; deduplicate
    seen: set = set()
    includes = []
    for inc in list(meta.comment_includes) + list(meta.includes):
        if inc and inc not in seen:
            seen.add(inc)
            includes.append(inc)

    if includes:
        meta.importStyle = "include"
        meta.importPaths = includes
        return

    # Fallback: use <relative path to source>
    meta.importStyle = "use"

    # Accept both new (source_file) and legacy (sourceFile) attribute names
    src_file = getattr(meta, "source_file", None) or getattr(meta, "sourceFile", "")
    base     = getattr(meta, "base_name", None)  or getattr(meta, "baseName",   os.path.basename(src_file))

    try:
        out_dir = os.path.dirname(output_scad_path)
        rel = os.path.relpath(src_file, out_dir).replace(os.sep, "/")
        if not rel.startswith("."):
            rel = "./" + rel
    except Exception:
        rel = base

    meta.importPaths = [rel]


class SCAD_Module_Dialog(QtWidgets.QDialog):
    """
    Dialog to inspect modules in a SCAD file and create a SCAD Module object.

    Accepts the new :class:`~freecad.OpenSCAD_Ext.parsers.scadmeta.ScadMeta`
    (modules as ``ScadModuleMeta`` with ``.params``) as well as the legacy
    ``SCADMeta`` (modules as ``SCADModule`` with ``.arguments``).
    """

    def __init__(self, meta, *args, **kwargs):
        parent = kwargs.pop("parent", None)
        super().__init__(parent)

        self.meta = meta
        self.selected_module = None
        self.arg_widgets = {}

        # Accept both new (source_file) and legacy (sourceFile) attribute names
        src_file = getattr(meta, "source_file", None) or getattr(meta, "sourceFile", "")
        self.setWindowTitle(f"SCAD Modules – {os.path.basename(src_file)}")
        self.resize(900, 700)

        write_log("Info", f"Opening SCAD_Module_Dialog for {src_file}")

        self._build_ui()
        self._populate_includes()
        self._populate_modules()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(8, 6, 8, 6)

        # Includes panels
        inc_layout = QtWidgets.QHBoxLayout()
        inc_layout.setSpacing(8)

        self.includes_box = self._make_list_panel("Includes / Uses")
        self.comment_includes_box = self._make_list_panel("Comment Includes")
        self._limit_panel_height(self.includes_box)
        self._limit_panel_height(self.comment_includes_box)

        inc_layout.addWidget(self.includes_box)
        inc_layout.addWidget(self.comment_includes_box)
        main_layout.addLayout(inc_layout)

        # Modules panel
        self.modules_box = self._make_list_panel("Modules")
        self._limit_panel_height(self.modules_box)
        # itemClicked fires on every click (even re-clicking the current item).
        # currentItemChanged handles keyboard navigation.
        self.modules_box.list.itemClicked.connect(self._on_module_item_clicked)
        self.modules_box.list.currentItemChanged.connect(self._on_module_selected)
        main_layout.addWidget(self.modules_box)

        # Module details
        self.details_box = QtWidgets.QGroupBox("Module Details")
        details_layout = QtWidgets.QVBoxLayout(self.details_box)
        details_layout.setContentsMargins(6, 4, 6, 4)
        self.details_label = QtWidgets.QLabel("")
        self.details_label.setWordWrap(True)
        details_layout.addWidget(self.details_label)
        self._limit_panel_height(self.details_box)
        main_layout.addWidget(self.details_box)

        # Arguments
        self.args_box = QtWidgets.QGroupBox("Arguments")
        args_layout = QtWidgets.QVBoxLayout(self.args_box)
        args_layout.setContentsMargins(6, 4, 6, 4)

        self.args_scroll = QtWidgets.QScrollArea()
        self.args_scroll.setWidgetResizable(True)
        self.args_container = QtWidgets.QWidget()
        self.args_grid = QtWidgets.QGridLayout(self.args_container)
        self.args_grid.setHorizontalSpacing(10)
        self.args_grid.setVerticalSpacing(4)
        self.args_grid.setColumnStretch(2, 1)
        self.args_scroll.setWidget(self.args_container)
        args_layout.addWidget(self.args_scroll)
        main_layout.addWidget(self.args_box, stretch=1)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        self.create_btn = QtWidgets.QPushButton("Create SCAD Module")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self._create_scad_module)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_list_panel(self, title):
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(6, 4, 6, 4)
        lst = QtWidgets.QListWidget()
        layout.addWidget(lst)
        box.list = lst
        return box

    def _limit_panel_height(self, widget, lines=4):
        fm = self.fontMetrics()
        widget.setMaximumHeight(fm.lineSpacing() * (lines + 2))

    # ------------------------------------------------------------------
    # Populate
    # ------------------------------------------------------------------

    def _populate_includes(self):
        for inc in self.meta.includes:
            self.includes_box.list.addItem(f"include <{inc}>")
        for inc in self.meta.comment_includes:
            self.comment_includes_box.list.addItem(inc)

    def _populate_modules(self):
        for mod in self.meta.modules:
            self.modules_box.list.addItem(mod.name)

    # ------------------------------------------------------------------
    # Module selection
    # ------------------------------------------------------------------

    def _on_module_item_clicked(self, item):
        """Handle mouse clicks – fires even when re-clicking the current item."""
        self._activate_module(item.text() if item else None)

    def _on_module_selected(self, current, previous):
        """Handle keyboard navigation via currentItemChanged."""
        if current:
            self._activate_module(current.text())

    def _activate_module(self, name):
        if not name:
            return

        mod = next((m for m in self.meta.modules if m.name == name), None)
        if mod is None:
            write_log("Warning", f"Module '{name}' not found in meta.modules")
            return

        self.selected_module = mod
        desc = mod.description or ""
        self.details_label.setText(desc if desc else "(no description)")
        self._build_argument_widgets()
        self.create_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Arguments
    # ------------------------------------------------------------------

    def _build_argument_widgets(self):
        """
        Rebuild the arguments grid for the currently selected module.

        Replaces the QScrollArea content widget entirely so there are no
        stale widgets from the previous selection (deleteLater() is async
        and can leave ghosts in the layout).
        """
        self.arg_widgets = {}

        # Support both new ScadModuleMeta (.params) and legacy SCADModule (.arguments)
        params = getattr(self.selected_module, "params", None)
        if not params:
            params = getattr(self.selected_module, "arguments", [])

        # Fresh container – avoids any stale-widget issues
        new_container = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(new_container)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(2, 1)

        for row, param in enumerate(params):
            name_lbl = QtWidgets.QLabel(param.name)

            value_widget = self._create_param_widget(param)

            desc_text = getattr(param, "description", "") or ""
            desc_lbl  = QtWidgets.QLabel(desc_text)
            desc_lbl.setWordWrap(True)

            grid.addWidget(name_lbl,     row, 0)
            grid.addWidget(value_widget, row, 1)
            grid.addWidget(desc_lbl,     row, 2)

            self.arg_widgets[param.name] = value_widget

        # Swap in the new container
        self.args_scroll.setWidget(new_container)
        self.args_container = new_container
        self.args_grid = grid

        if not params:
            grid.addWidget(QtWidgets.QLabel("(no parameters)"), 0, 0)

        write_log("Info", f"Built {len(params)} argument widget(s) for '{self.selected_module.name}'")

    def _create_param_widget(self, param):
        default = param.default

        if default in ("true", "false"):
            w = QtWidgets.QCheckBox()
            w.setChecked(default == "true")
            return w

        try:
            if default is not None and "." not in str(default):
                spin = QtWidgets.QSpinBox()
                spin.setRange(-10_000_000, 10_000_000)
                spin.setValue(int(default))
                return spin
        except Exception:
            pass

        try:
            if default is not None:
                dspin = QtWidgets.QDoubleSpinBox()
                dspin.setRange(-1e9, 1e9)
                dspin.setDecimals(6)
                dspin.setValue(float(default))
                return dspin
        except Exception:
            pass

        line = QtWidgets.QLineEdit()
        if default is not None:
            line.setText(str(default).strip('"'))
        return line

    # ------------------------------------------------------------------
    # Create SCAD Module Object
    # ------------------------------------------------------------------

    def _collect_args(self):
        args = {}
        for name, widget in self.arg_widgets.items():
            if isinstance(widget, QtWidgets.QCheckBox):
                args[name] = widget.isChecked()
            elif isinstance(widget, QtWidgets.QSpinBox):
                args[name] = widget.value()
            elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                args[name] = widget.value()
            else:
                args[name] = widget.text()
        return args

    def _clean_module_name(self, name):
        return name[:-2] if name.endswith("()") else name

    def _create_scad_module(self):
        if not self.selected_module:
            return

        write_log("Info", f"Creating SCAD module object: {self.selected_module.name}")

        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument("SCAD_Import")

        module_name = self._clean_module_name(self.selected_module.name)
        source_dir  = BaseParams.getScadSourcePath()
        source_file = os.path.join(source_dir, module_name + ".scad")

        _finalize_meta_imports(self.meta, source_file)

        obj = doc.addObject("Part::FeaturePython", module_name)
        obj.Label = module_name
        ViewSCADProvider(obj.ViewObject)

        args = self._collect_args()
        SCADModuleObject(
            obj,
            module_name,
            source_file,
            self.meta,
            self.selected_module,
            args,
        )

        doc.recompute()
        self.accept()
