from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase, ViewSCADProvider
# --------------------------------------------------------
# SCAD Project object
# --------------------------------------------------------

class SCADProjectObject(SCADfileBase):
    def __init__(self, obj, name, sourceFile, meta, module, args):

        super().__init__(
            obj,
            scadName="Project",
            sourceFile=sourceFile,
            default_mode="AST_Brep",
        )

        self.meta = meta
        self.module = module
        self.args = args

        #self._project_ui_policy(obj)

class SCADProjectObject(SCADfileBase):
    def __init__(self, obj, name, sourceFile, meta=None, module=None, args=None):
        # Project always defaults mode to AST-Brep
        super().__init__(obj, scadName=name, sourceFile=sourceFile, mode="AST-Brep")

        self.Object = obj
        self.meta = meta
        self.module = module
        self.args = args

        obj.Proxy = self

        # Initialize project-specific properties
        self._init_project_properties(obj)

    def _init_project_properties(self, obj):
        return

    def onChanged(self, fp, prop):
        return


    def clean_module_name(self, name: str) -> str:
        return name[:-2] if name.endswith("()") else name

    def execute(self, obj):
        """
        Hook for OpenSCAD execution (can be implemented later).
        """
        return