# SCAD_Module_Dialog.py

from PySide2 import QtWidgets, QtCore
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase
import FreeCAD

class SCAD_Module_Dialog(QtWidgets.QDialog):
    def __init__(self, meta, parent=None):
        super().__init__(parent)
        self.meta = meta
        self.selected_module = None
        write_log("Info", f"Initializing SCADModuleDialog for file: {meta.fileName}")
        self.setWindowTitle(f"SCAD Modules - {meta.fileName}")
        self.resize(1000, 600)
        self.init_ui()

    def init_ui(self):
        # Prevent multiple layout assignment
        if self.layout():
            return

        main_layout = QtWidgets.QHBoxLayout()

        # --- Left Column: Includes, Modules, Module Detail ---
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)

        # Includes list
        self.includes_list = QtWidgets.QListWidget()
        self.includes_list.addItems(self.meta.includes)
        left_layout.addWidget(QtWidgets.QLabel("Includes"))
        left_layout.addWidget(self.includes_list)

        # Modules list
        self.modules_list = QtWidgets.QListWidget()
        self.modules_list.addItems([m.name for m in self.meta.modules])
        self.modules_list.currentRowChanged.connect(self.module_selected)
        left_layout.addWidget(QtWidgets.QLabel("Modules"))
        left_layout.addWidget(self.modules_list)

        # Module detail
        self.module_detail = QtWidgets.QTextEdit()
        self.module_detail.setReadOnly(True)
        left_layout.addWidget(QtWidgets.QLabel("Module Description"))
        left_layout.addWidget(self.module_detail)

        # --- Right Column: Header Includes + Arguments Table ---
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)

        # Header comment includes
        self.comment_includes = QtWidgets.QListWidget()
        self.comment_includes.addItems(self.meta.comment_includes)
        right_layout.addWidget(QtWidgets.QLabel("File Comment Includes"))
        right_layout.addWidget(self.comment_includes)

        # Arguments table
        self.arguments_table = QtWidgets.QTableWidget()
        self.arguments_table.setColumnCount(3)
        self.arguments_table.setHorizontalHeaderLabels(["Name", "Default", "Description"])
        self.arguments_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.arguments_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.arguments_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        right_layout.addWidget(QtWidgets.QLabel("Arguments"))
        right_layout.addWidget(self.arguments_table)

        # Add columns to main layout
        main_layout.addWidget(left_widget, 3)
        main_layout.addWidget(right_widget, 2)  # Make right column wider

        # --- Buttons ---
        btn_layout = QtWidgets.QHBoxLayout()
        self.create_btn = QtWidgets.QPushButton("Create SCAD Object")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self.create_scad_object)
        btn_layout.addStretch()
        btn_layout.addWidget(self.create_btn)

        # --- Final layout ---
        main_vlayout = QtWidgets.QVBoxLayout()
        main_vlayout.addLayout(main_layout)
        main_vlayout.addLayout(btn_layout)
        self.setLayout(main_vlayout)

    # --- Module selection ---
    def module_selected(self, index):
        if index < 0:
            return

        module = self.meta.modules[index]
        self.selected_module = module
        write_log("Info", f"Module selected: {module.name}")

        # Module description
        self.module_detail.setPlainText(module.description or "")

        # Populate arguments table
        self.arguments_table.setRowCount(len(module.arguments))
        for row, arg in enumerate(module.arguments):
            self.arguments_table.setItem(row, 0, QtWidgets.QTableWidgetItem(arg.name))
            self.arguments_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(arg.default or "")))
            self.arguments_table.setItem(row, 2, QtWidgets.QTableWidgetItem(arg.description or ""))

        # Enable SCAD object creation
        self.create_btn.setEnabled(True)

    # --- Create SCAD Object in FreeCAD ---
    def create_scad_object(self):
        if not self.selected_module:
            write_log("Info", "No module selected for SCAD object creation")
            return

        obj_name = self.selected_module.name
        write_log("Info", f"Creating SCADModuleObject: {obj_name}")

        doc = FreeCAD.ActiveDocument
        if not doc:
            doc = FreeCAD.newDocument()

        obj = doc.addObject("Part::FeaturePython", obj_name)
        SCADModuleObject(obj, self.meta, self.selected_module)
        doc.recompute()
        write_log("Info", f"SCADModuleObject '{obj_name}' created successfully")


# --- SCADModuleObject for FreeCAD ---
class SCADModuleObject(SCADfileBase):
    def __init__(self, obj, meta, module):
        write_log("Info", f"Initializing SCADModuleObject: {module.name}")
        self.Object = obj
        obj.Proxy = self
        self._init_properties(obj, meta, module)
        self._set_defaults(obj, module)

    def _init_properties(self, obj, meta, module):
        # --- Parameters group ---
        obj.addProperty("App::PropertyString", "ModuleName", "Parameters", "OpenSCAD module name").ModuleName = module.name
        obj.addProperty("App::PropertyString", "Description", "Parameters", "Module description").Description = module.description or ""
        obj.setEditorMode("Description", 1)
        obj.addProperty("App::PropertyString", "Usage", "Parameters", "Usage examples").Usage = "\n".join(getattr(module, "usage", []))
        obj.setEditorMode("Usage", 1)

        # Arguments info
        arg_info = []
        for arg in getattr(module, "arguments", []):
            line = arg.name
            if getattr(arg, "description", None):
                line += " – " + arg.description
            arg_info.append(line)
        obj.addProperty("App::PropertyString", "ArgumentsInfo", "Parameters", "Argument documentation").ArgumentsInfo = "\n".join(arg_info)
        obj.setEditorMode("ArgumentsInfo", 1)

        # --- SCAD group ---
        obj.addProperty("App::PropertyStringList", "Includes", "SCAD", "Required include files").Includes = getattr(meta, "includes", [])
        obj.addProperty("App::PropertyString", "Source", "SCAD", "Generated OpenSCAD source")
        obj.setEditorMode("Source", 1)

        # Add module arguments dynamically
        for arg in getattr(module, "arguments", []):
            self._add_argument_property(obj, arg)

    def _set_defaults(self, obj, module):
        obj.ModuleName = module.name

    def execute(self, obj):
        src = self._build_scad_source(obj)
        obj.Source = src
        write_log("Info", f"SCAD source built for {obj.ModuleName}")

    def _build_scad_source(self, obj):
        lines = [f'include <{inc}>;' for inc in obj.Includes]
        lines.append("")
        lines.append(f"{obj.ModuleName}(")

        args = []
        for prop in obj.PropertiesList:
            if obj.getGroupOfProperty(prop) != "Parameters":
                continue
            if prop in ("ModuleName", "Description", "ArgumentsInfo", "Usage"):
                continue
            val = getattr(obj, prop)
            if val != "":
                args.append(f"    {prop} = {val}")
        lines.append(",\n".join(args))
        lines.append(");")
        return "\n".join(lines)

    def _add_argument_property(self, obj, arg):
        name = arg.name
        default = getattr(arg, "default", None)
        desc = getattr(arg, "description", "")
        # Boolean
        if default in ("true", "false"):
            prop = obj.addProperty("App::PropertyBool", name, "Parameters", desc)
            setattr(obj, name, default == "true")
            return
        # Integer
        try:
            if default is not None and "." not in str(default):
                ival = int(default)
                obj.addProperty("App::PropertyInteger", name, "Parameters", desc)
                setattr(obj, name, ival)
                return
        except Exception:
            pass
        # Float
        try:
            fval = float(default)
            obj.addProperty("App::PropertyFloat", name, "Parameters", desc)
            setattr(obj, name, fval)
            return
        except Exception:
            pass
        # String fallback
        obj.addProperty("App::PropertyString", name, "Parameters", desc)
        if default:
            setattr(obj, name, str(default).strip('"'))

