#**************************************************************************
#*                                                                         *
#*   Copyright (c) 2023 Keith Sloan <keith@sloan-home.co.uk>               *
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Library General Public License for more details.                  *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         * 
#*   Acknowledgements :                                                    *
#*                                                                         *
#***************************************************************************

import FreeCAD, FreeCADGui, Part, Mesh
import os, tempfile
from pathlib import Path

from PySide import QtGui, QtWidgets
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.core.OpenSCADUtils import callopenscad, \
                                               OpenSCADError
from freecad.OpenSCAD_Ext.importers import importAltCSG
from freecad.OpenSCAD_Ext.importers import importASTCSG

def create_scad_object(title, newFile, sourceFile, scadName="SCAD_Object"):
    write_log("Info",f"create scad object  ; newFile {newFile} scadName = {scadName} sourceFile = {sourceFile}")
    QtGui.QGuiApplication.setOverrideCursor(QtGui.Qt.ArrowCursor)
    dialog = OpenSCADeditOptions(scadName, sourceFile, newFile)
    result = dialog.exec_()
    QtGui.QGuiApplication.restoreOverrideCursor()
    if result != QtGui.QDialog.Accepted:
        pass
    write_log("Info","Action")
    options = dialog.getValues()
    write_log("Info",f"Options {options}") 

    # Create SCAD Object
    scadName = dialog.getName()
    sourceFile = dialog.get_sourceFile()
    scadObj = dialog.create_from_dialog(scadName)
    if scadObj:
        scadObj.editFile(sourceFile)

# Shared between SCADObject and SCADModule
def createMesh(srcObj, wrkSrc, d_params=None):
    """Run OpenSCAD to generate an STL and return a Mesh.Mesh object.

    Returning Mesh.Mesh (not Part.Shape) keeps the result out of FreeCAD 1.1's
    TNP element-map pipeline, which would otherwise spin indefinitely when
    indexing the thousands of triangles in a complex mesh on every selection.
    """
    print(f"Create Mesh {srcObj.Name} {wrkSrc}")
    if d_params:
        print(f"  -D overrides: {d_params}")
    try:
        tmpDir = tempfile.gettempdir()
        tmpOutFile = os.path.join(tmpDir, srcObj.Name+'.stl')
        print(f"Call OpenSCAD - Input file {wrkSrc} Output file {tmpOutFile}")
        tmpFileName = callopenscad(wrkSrc,
            outputfilename=tmpOutFile, outputext='stl',
            timeout=int(srcObj.timeout), d_params=d_params)
        if os.path.exists(tmpFileName):
            mesh = Mesh.Mesh()
            mesh.read(tmpFileName)
            print(f"Mesh facets={mesh.CountFacets} solid={mesh.isSolid()}")
            try:
                os.unlink(tmpFileName)
            except OSError:
                pass
            return mesh          # ← Mesh.Mesh, not Part.Shape

    except OpenSCADError as e:
        #print(f"OpenSCADError {e} {e.value}")
        before = e.value.split('in file',1)[0]
        print(f"Before : {before}")
        after = e.value.rsplit(',',1)[1]
        print(f"After  : {after}")
        after = after.splitlines()[0]
        print(f"After  : {after}")
        srcObj.message = before + after
        print(f"End After - Error Message {srcObj.message}")
        #FreeCAD.closeDocument("work")
        # work document is for Brep Only
        srcObj.execute = False

# Source may be processed
def createBrep(srcObj, mode, tmpDir, wrkSrc, d_params=None):

    print(f"Create Brep {srcObj.scadName} {srcObj.fnmax}")
    if d_params:
        print(f"  -D overrides: {d_params}")
    actDoc = FreeCAD.activeDocument().Name
    print(f"Active Document {actDoc}")
    wrkDoc = FreeCAD.newDocument("work")
    try:
        print(f"Source : {srcObj.scadName}")
        print(f"SourceFile : {srcObj.sourceFile}")
        csgOutFile = os.path.join(tmpDir, srcObj.Name+'.csg')
        # brepOutFile = os.path.join(tmpDir, srcObj.Name+'.brep')
        print("Call OpenSCAD to create csg file from scad")
        tmpFileName=callopenscad(wrkSrc, \
			outputfilename=csgOutFile, outputext='csg', \
			timeout=int(srcObj.timeout), d_params=d_params)
        if hasattr(srcObj, "source"):
            source = srcObj.scadName
        if hasattr(srcObj, "sourceFile"):
        	source = srcObj.sourceFile    
        pathName = os.path.dirname(os.path.normpath(srcObj.scadName))
        print(f"Process CSG File Mode {mode} name path {pathName} file {tmpFileName}")
		
        #processCSG(wrkDoc, pathName, tmpFileName, srcObj.fnmax)
        if mode == 'AST-Brep':
            importASTCSG.processCSG(wrkDoc, tmpFileName, srcObj.fnmax)

        elif mode == 'Brep':
            importAltCSG.processCSG(wrkDoc, tmpFileName, srcObj.fnmax)
            # *** Does not work for earrings.scad
        shapes = []
        retShape = Part.Shape()     # Empty Shape
        for cnt, obj in enumerate(wrkDoc.RootObjects, start=0):
            if hasattr(obj, "Shape"):
                shapes.append(obj.Shape)
                print(f"Shapes in WrkDoc {cnt}")        
            if cnt > 1:
                retShape = Part.makeCompound(shapes)
            else:
                retShape = shapes[0]
        print(f"CreateBrep Shape {retShape}")
		#links = []
		#for cnt, obj in enumerate(wrkDoc.RootObjects):
		#    if hasattr(obj, "Shape"):
		#        links.append(obj)
		#print(f"Number of Objects {len(wrkDoc.RootObjects)} {cnt}")        
		#if cnt > 1:
		#    retObj = wrkDoc.addObject("Part::Compound","Compound")
		#    retObj.Links = links
		#    #if not retObj.Shape.isValid():
		#    #    print(f"Make Compound Failed")
		#    #    retObj.Shape.check()
		#    #    return
		#else:
		#    retObj = wrkDoc.RootObjects[0]    
        if srcObj.keep_work_doc is not True:
            FreeCAD.closeDocument("work")
		# restore active document 
        print(f"Set Active Document {actDoc}")
        FreeCAD.setActiveDocument(actDoc)
		#FreeCADGui.SendMsgToActiveView("ViewFit")
		#print(f"Ret Obj {retObj.Name} Shape {retObj.Shape}")
        print(f"Ret Shape {retShape}")
        return retShape
		#return retObj

    except OpenSCADError as e:
		#print(f"OpenSCADError {e} {e.value}")
        before = e.value.split('in file',1)[0]
        print(f"Before : {before}")
        after = e.value.rsplit(',',1)[1]
        print(f"After  : {after}")
        after = after.splitlines()[0]
        print(f"After  : {after}")
        srcObj.message = before + after
        print(f" End After - Error Message {srcObj.message}")
        FreeCAD.closeDocument("work")
        srcObj.execute = False


# def scanForModules(appendFp, sourceFp, module):
#    print(f"Scan for Modules")
#    print(FreeCAD.ActiveDocument.Objects)
#    for obj in FreeCAD.ActiveDocument.Objects:
#        print(f"get Source {obj.Label}")
#        # Proxy has functions but need to pass Object with properties
#        if hasattr(obj, "Proxy"):
#            if hasattr(obj.Proxy, "getSource"):
#                src = obj.Proxy.getSource(obj)
#                if src is not None:
#                    print(f"Module Source : {src}")
#                    #source += src
#                    appendFp.write(src)
#
#    # Is this a SCADModule
#    if module == True:
#        print("add mod call")
#        src = srcObj.name + '('
#        if len(srcObj.variables) > 0:
#            for v in srcObj.variables[:-1]:
#                src = src + v + ','
#                src = src + srcObj.variables[-1]
#        src = src +');'
#        print(f"mod call {src}")
#        appendFp.write(src)
#    source = sourceFp.read()
#    appendFp.write(source)


def _get_linked_varset(fp):
    """
    Resolve the linked VarSet for *fp*.

    ``linked_varset`` is stored as a plain string (App::PropertyString) holding
    the VarSet's internal FreeCAD object name.  This avoids the App::PropertyLink
    dependency edge that causes FC 1.1+ TNP to flag the SCAD object as Touched
    on every document graph walk, which would spin the cursor indefinitely.

    Returns the App::VarSet object, or None if not set / not found.
    """
    name = getattr(fp, 'linked_varset', None)
    if not name:
        return None
    try:
        return fp.Document.getObject(name)
    except Exception:
        return None


def shapeFromSourceFile(srcObj, module=False, modules=False):
    print(f"shapeFrom Source File : keepWork {srcObj.keep_work_doc}")
    tmpDir = tempfile.gettempdir()
    wrkSrc = srcObj.sourceFile

    print(f"source name {srcObj.Label} mode {srcObj.mode}")

    # Build -D overrides from linked VarSet (if any)
    d_params = None
    varset = _get_linked_varset(srcObj)
    if varset is not None:
        from freecad.OpenSCAD_Ext.core.varset_utils import varset_to_D_params
        d_params = varset_to_D_params(varset) or None
        if d_params:
            write_log("SCADfileBase", f"Applying {len(d_params)} VarSet override(s)")

    if srcObj.mode in ["Brep", "AST-Brep"]:
        brepShape = createBrep(srcObj, srcObj.mode, tmpDir, wrkSrc, d_params=d_params)
        print(f"Active Document {FreeCAD.ActiveDocument.Name}")
        return brepShape

    elif srcObj.mode == "Mesh":
        print(f"wrkSrc {wrkSrc}")
        return createMesh(srcObj, wrkSrc, d_params=d_params)

# Cannot put in self as SCADlexer is not JSON serializable
# How to make static ???
def parse(obj, src):
    from scadLexer import SCADlexer
    from scadParser import SCADparser
    scadlexer = SCADlexer()
    scadparser = SCADparser(obj, scadlexer)
    parser = scadparser.parser
    #parser.parse(obj.definition, debug=True)
    parser.parse(src)
    #obj.setEditorMode("text",2)


class EditTextValue(QtGui.QWidget):
    def __init__(self, label="", default="", parent=None):
        super(EditTextValue, self).__init__(parent)

        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QtGui.QLabel(label)
        layout.addWidget(self.label)

        self.textName = QtGui.QLineEdit(default)
        #self.textName.setPlaceholderText(default"Enterfilename")
        layout.addWidget(self.textName, 1)
        self.textName.editingFinished.connect(self.getVal)
        self.show()

    def getVal(self):
        return self.textName.text()

class GeometryType(QtGui.QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QtGui.QHBoxLayout()
        self.label = QtGui.QLabel('Geometry Type')
        self.layout.addWidget(self.label)
        self.importType = QtGui.QComboBox()
        self.importType.addItem('Mesh')
        self.importType.addItem('AST-Brep')
        self.importType.addItem('Brep')
        self.layout.addWidget(self.importType)
        self.setLayout(self.layout)

    def getVal(self):
        return self.importType.currentText()
                     
class IntegerValue(QtGui.QWidget):
	def __init__(self, label, value):
		super().__init__()
		self.layout = QtGui.QHBoxLayout()
		self.label = QtGui.QLabel(label)
		self.value = QtGui.QLineEdit()
		self.value.setText(str(value))
		self.layout.addWidget(self.label)
		self.layout.addWidget(self.value)
		self.setLayout(self.layout)

	def getVal(self):
		return int(self.value.text())

class BooleanValue(QtGui.QWidget):
	def __init__(self, label, value):
		super().__init__()
		self.layout = QtGui.QHBoxLayout()
		self.label = QtGui.QLabel(label)
		self.value = QtGui.QRadioButton()
		self.value.setChecked(value)
		self.layout.addWidget(self.label)
		self.layout.addWidget(self.value)
		self.setLayout(self.layout)

	def getVal(self):
		if self.value.isChecked():
			return True
		else:
			return False


class OpenSCADeditOptions(QtWidgets.QDialog):
    def __init__(self, newFile=True, sourceFile=None, parent=None):
        super().__init__(parent)
        self.newFile = newFile
        self.sourceFile = sourceFile  # Only known if editing an existing file

        self.setWindowTitle("SCAD File Options")
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        # ---------- SCAD Name ----------
        if self.newFile:
            # User must type the new file name
            scadNameVal = ""
            readOnly = False
        else:
            # Existing file → read-only stem
            scadNameVal = Path(sourceFile).stem
            readOnly = True

        self.scadName = EditTextValue("SCAD Name", default=scadNameVal, readOnly=readOnly)
        self.layout.addWidget(self.scadName)

        # ---------- Other fields ----------
        self.geometryType = GeometryType()
        self.layout.addWidget(self.geometryType)

        self.fnMax = IntegerValue("FnMax", 16)
        self.layout.addWidget(self.fnMax)

        self.timeOut = IntegerValue("TimeOut", 30)
        self.layout.addWidget(self.timeOut)

        self.keepOption = BooleanValue("Keep File", False)
        self.layout.addWidget(self.keepOption)

        # ---------- OK / Cancel ----------
        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.layout.addWidget(self.buttonBox)


    # ---------- collect values ----------
    def getValues(self):
        scadName = self.scadName.getVal().strip()

        if self.newFile:
            # Generate full sourceFile path from workbench preference + user-provided name
            sourceDir = BaseParams.getScadSourcePath()  # <- your preference path
            self.sourceFile = str(Path(sourceDir) / scadName)
        # else: sourceFile already set for editing

        return {
            "scadName": scadName,
            "geometryType": self.geometryType.getVal(),
            "fnMax": self.fnMax.getVal(),
            "timeOut": self.timeOut.getVal(),
            "keepOption": self.keepOption.getVal(),
            "newFile": self.newFile,
            "sourceFile": self.sourceFile,
        }



def create_from_dialog(self, sourceFile, newFile=True):
    return create_scad_object(
        sourceFile=sourceFile,
        geometryType=self.geometryType.getVal(),
        fnMax=self.fnMax.getVal(),
        timeOut=self.timeOut.getVal(),
        keepOption=self.keepOption.getVal(),
        newFile=newFile
    )

    def getName(self):
        return self.scadName.getVal()

    def get_sourceFile(self):
        return self.sourceFile

    def onCancel(self):
        self.result = 'cancel'
        #QtGui.QGuiApplication.restoreOverrideCursor()

    def onOk(self):
        self.result = 'ok'
        #QtGui.QGuiApplication.restoreOverrideCursor()
# --- DIAG startup marker ---
import datetime as _diag_dt
with open("/tmp/scad_diag.log", "a") as _diag_f:
    _diag_f.write(f"\n=== SCADObject module loaded {_diag_dt.datetime.now()} ===\n")
    _diag_f.flush()

class SCADfileBase:
    IMPORT_MODE = ["Mesh", "AST-Brep", "Brep"]

    def __init__(self, obj, scadName, sourceFile, mode="Mesh", fnmax=16, timeout=30, keep=False):
        self._initializing = True   # suppress onChanged rendering during setup
        self.Object = obj
        obj.Proxy = self

        # 1. Ensure properties exist
        self._init_properties(obj,scadName, sourceFile, mode, fnmax, timeout, keep)
        modeList = SCADfileBase.IMPORT_MODE
        obj.scadName = scadName
        obj.setEditorMode("scadName",1)
        obj.sourceFile = sourceFile
        obj.modules = True
        modeIdx = modeList.index(mode)
        obj.mode = modeList
        obj.mode = modeIdx
        obj.mesh_recombine = False
        self._initializing = False  # setup complete — onChanged may now render

    def _init_properties(self, obj, scadName, sourceFile, mode, fnmax, timeout, keep):
        super().__init__()
        self.Object = obj      # ← REQUIRED in your case
        obj.addProperty("App::PropertyString","scadName","OpenSCAD","OpenSCAD scadObject")
        obj.addProperty("App::PropertyFile","sourceFile","OpenSCAD","OpenSCAD source")
        obj.addProperty("App::PropertyString","message","OpenSCAD","OpenSCAD message")
        obj.addProperty("App::PropertyBool","modules","OpenSCAD","OpenSCAD Uses Modules")
        obj.addProperty("App::PropertyBool","edit","OpenSCAD","Edit SCAD source")
        obj.addProperty("App::PropertyBool","execute","OpenSCAD","Process SCAD source")
        obj.addProperty("App::PropertyEnumeration","mode","OpenSCAD","mode - create Brep or Mesh")
        obj.addProperty("App::PropertyInteger","fnmax","OpenSCAD","Max Poylgon - If circle or cylinder has more than this number of sides, treat as circle or cyliner")
        obj.fnmax = fnmax
        obj.addProperty("App::PropertyBool","mesh_recombine","OpenSCAD","Mesh Recombine")
        obj.addProperty("App::PropertyBool","keep_work_doc","OpenSCAD","Keep FC Work Document")
        obj.keep_work_doc = keep
        obj.addProperty("App::PropertyInteger","timeout","OpenSCAD","OpenSCAD process timeout (secs)")
        obj.timeout = timeout
        obj.addProperty("App::PropertyString","linked_varset","OpenSCAD",
                        "Name of the VarSet whose properties override SCAD variables via -D on execution")
        obj.addProperty("App::PropertyString","companion_mesh","OpenSCAD",
                        "Name of companion Mesh::Feature used for Mesh-mode display (avoids TNP)")

    def onChanged(self, fp, prop):

        if getattr(self, '_initializing', False):
            return

        if "Restore" in fp.State:
            return

        # DIAG: log every property change so we can see what FC 1.1 is touching
        import datetime as _dt
        _oc_line = (f"{_dt.datetime.now().strftime('%H:%M:%S.%f')} "
                    f"onChanged obj={fp.Label} state={list(fp.State)} prop={prop}\n")
        with open("/tmp/scad_diag.log", "a") as _f:
            _f.write(_oc_line)
            _f.flush()

        if prop == "Shape":
            return

        # Mode changes are NOT auto-rendered — FreeCAD refreshes enumeration
        # properties on selection which would trigger a spurious OpenSCAD run.
        # Set execute=True to re-render after changing mode.

        if prop == "execute" and fp.execute:
            self.executeFunction(fp)
            fp.execute = False
            from PySide.QtCore import QTimer
            QTimer.singleShot(200, lambda: FreeCADGui.SendMsgToActiveView("ViewFit"))

        if prop == "edit":
            if fp.edit:
                self.editFile(fp.sourceFile)
                fp.edit = False
            FreeCADGui.Selection.addSelection(fp)

        # message: just log — updateGui() here causes re-entrant onChanged
        # loops in FreeCAD 1.1.x by processing pending Qt events mid-handler.


    def execute(self, fp):
        '''Called by FreeCAD recompute. Never runs OpenSCAD.'''
        import traceback as _tb, datetime as _dt
        _n = getattr(self, '_execute_count', 0) + 1
        self._execute_count = _n
        with open("/tmp/scad_diag.log", "a") as _f:
            _f.write(f"{_dt.datetime.now().strftime('%H:%M:%S.%f')} "
                     f"execute #{_n} {getattr(fp,'Name','?')} "
                     f"state={list(fp.State)} "
                     f"cached={getattr(self,'_cached_shape',None) is not None}\n")
            _f.flush()
        if "Restore" in fp.State:
            return
        # Always set fp.Shape so FC clears the Touched flag.
        # For Mesh mode _cached_shape is None → empty shape is fine;
        # the companion Mesh::Feature holds the actual geometry.
        cached = getattr(self, '_cached_shape', None)
        fp.Shape = cached if cached is not None else Part.Shape()

    # use name render for new workbench
    # redirect for compatibility with old Alternate
    #
    def renderFunction(self, obj):
        write_log("Info","Render Function")
        self.executeFunction(obj)


    def executeFunction(self, obj):
        import traceback as _tb, datetime as _dt
        _fn = getattr(self, '_execfn_count', 0) + 1
        self._execfn_count = _fn
        _line = (f"{_dt.datetime.now().strftime('%H:%M:%S.%f')} "
                 f"executeFunction #{_fn} obj={getattr(obj,'Name','?')}\n"
                 + ''.join(_tb.format_stack(limit=8)))
        with open("/tmp/scad_diag.log", "a") as _f:
            _f.write(_line + "---\n")
            _f.flush()
        from timeit import default_timer as timer
        write_log("SCADfileBase",f"Execute {obj.Name} Mode {obj.mode} keepWork {obj.keep_work_doc}")
        start = timer()

        # Snapshot the VarSet params used for this run so execute() can detect
        # whether the values have changed before deciding to re-run OpenSCAD.
        # Stored before the run so that even a failed run suppresses redundant
        # retries (the shape will be None, which is the other half of the guard).
        _varset = _get_linked_varset(obj)
        if _varset is not None:
            from freecad.OpenSCAD_Ext.core.varset_utils import varset_to_D_params
            self._last_d_params = sorted(varset_to_D_params(_varset))
        else:
            self._last_d_params = None

        obj.message = ""
        result = shapeFromSourceFile(obj, modules=obj.modules)

        if isinstance(result, Mesh.Mesh):
            # Mesh mode: store mesh on proxy and create/update companion Mesh::Feature.
            # The FeaturePython itself keeps an EMPTY Part.Shape so FreeCAD's TNP
            # never indexes mesh triangles → no spinning cursor on selection.
            self._cached_mesh   = result
            self._cached_shape  = None
            obj.Shape = Part.Shape()        # empty — companion provides display
            companion_name = getattr(obj, 'companion_mesh', '')
            companion = obj.Document.getObject(companion_name) if companion_name else None
            if companion is None:
                companion       = obj.Document.addObject("Mesh::Feature", obj.Label)
                obj.companion_mesh = companion.Name
                # Hide the FeaturePython from the 3D view; companion shows geometry
                try:
                    obj.ViewObject.Visibility = False
                except AttributeError:
                    pass
            companion.Mesh = result
            try:
                companion.ViewObject.DisplayMode = "Shaded"
            except (ValueError, AttributeError):
                pass

        elif result is not None:
            # Brep / AST-Brep: standard Part.Shape path.
            # If the object previously ran in Mesh mode it may have a companion
            # Mesh::Feature.  Remove it so only the FeaturePython is visible.
            companion_name = getattr(obj, 'companion_mesh', '')
            if companion_name:
                companion = obj.Document.getObject(companion_name)
                if companion is not None:
                    write_log("SCADfileBase",
                        f"Removing stale companion '{companion_name}' "
                        f"(mode switched to BRep)")
                    obj.Document.removeObject(companion_name)
                obj.companion_mesh = ''

            self._cached_shape = result
            self._cached_mesh  = None
            obj.Shape = result
            try:
                obj.ViewObject.Visibility = True
                obj.ViewObject.DisplayMode = u"Shaded"
            except (ValueError, AttributeError):
                pass

        else:
            # OpenSCAD failed — clear everything
            self._cached_shape = None
            self._cached_mesh  = None
            obj.Shape = Part.Shape()

        obj.execute = False
        end = timer()
        print(f"==== Create Shape took {end-start} secs ====")
        FreeCADGui.Selection.addSelection(obj)


    def editFunction(self, new_file=False):
        obj = self.Object

        if not hasattr(obj, "sourceFile"):
            FreeCAD.Console.PrintError("SCAD object has no sourceFile\n")
            return

        self.editFile(obj.sourceFile, new_file=new_file)


    def editFile(self, fname, new_file=False):  # For compatibility with legacy
        import FreeCAD
        import subprocess, os, sys
        editorPathName = FreeCAD.ParamGet(\
            "User parameter:BaseApp/Preferences/Mod/OpenSCAD").GetString('externalEditor')
        print(f"Path to external editor {editorPathName}")

        # Seed from the Resources template when the file is genuinely new:
        #   - file doesn't exist yet, OR
        #   - file exists but is empty (leftover from a cancelled/failed session)
        # Never overwrite a file that already has content, even when new_file=True
        # (the user may have deliberately chosen an existing filename).
        file_is_new = not os.path.exists(fname) or os.path.getsize(fname) == 0
        if file_is_new:
            write_log("SCADfileBase", f"Seeding new SCAD file from template: {fname}")
            scad_name = os.path.splitext(os.path.basename(fname))[0]
            template_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "Resources", "new_scad_template.scad"
            )
            try:
                if os.path.exists(template_path):
                    with open(template_path, "r", encoding="utf-8") as tf:
                        content = tf.read()
                    # Replace the {{NAME}} placeholder with the actual file name
                    content = content.replace("{{NAME}}", scad_name)
                    with open(fname, "w", encoding="utf-8") as f:
                        f.write(content)
                    write_log("SCADfileBase", f"Template copied from {template_path}")
                else:
                    write_log("SCADfileBase",
                        f"Template not found at {template_path} — writing minimal fallback")
                    with open(fname, "w", encoding="utf-8") as f:
                        f.write(f"// {scad_name}.scad\n\ncube([10, 10, 10]);\n")
            except Exception as e:
                write_log("SCADfileBase", f"Could not seed template: {e}")

        # ToDo : Check pathname valid
        if editorPathName != "":
            p1 = subprocess.Popen( \
                [editorPathName, fname], \
                stdin=subprocess.PIPE,\
                stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        else:
            print(f"External Editor preference editorPathName not set")

    def editOpenStudio(self):       # Dummy so can change later
        write_log("SCADfileBase","Edit OpenSCAD Studio")
        self.open_in_openscad_studio()

    def open_in_openscad_studio(self):
        import sys, subprocess, os
        write_log("SCADfileBase","Open in openscad studio")
        obj = self.Object

        scad_path = obj.sourceFile

        # Ensure .scad extension
        if not scad_path.lower().endswith(".scad"):
            scad_path = scad_path + ".scad"
            obj.sourceFile = scad_path  # keep object consistent

        # Ensure file exists on disk — seed from Resources template if missing/empty
        if not os.path.exists(scad_path) or os.path.getsize(scad_path) == 0:
            write_log("openscad studio", f"Seeding new SCAD file from template: {scad_path}")
            scad_name = os.path.splitext(os.path.basename(scad_path))[0]
            template_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "Resources", "new_scad_template.scad"
            )
            try:
                if os.path.exists(template_path):
                    with open(template_path, "r", encoding="utf-8") as tf:
                        content = tf.read()
                    content = content.replace("{{NAME}}", scad_name)
                    with open(scad_path, "w", encoding="utf-8") as f:
                        f.write(content)
                else:
                    with open(scad_path, "w", encoding="utf-8") as f:
                        f.write(f"// {scad_name}.scad\n\ncube([10, 10, 10]);\n")
            except Exception as e:
                write_log("openscad studio", f"Could not seed template: {e}")

        # Extra safety: ensure it’s readable
        os.chmod(scad_path, 0o644)

        scad_path = obj.sourceFile  
        write_log("openscad studio",f"Platform {sys.platform} ScadPath {scad_path}")

        if sys.platform == "darwin":
            subprocess.Popen([
                "open",
                "-a", "/Applications/OpenSCAD Studio.app",
                scad_path
            ])

        elif sys.platform.startswith("linux"):
            subprocess.Popen([
                "openscad-studio",
                scad_path
            ])

        elif sys.platform.startswith("win"):
            subprocess.Popen([
                r"C:\Program Files\OpenSCAD Studio\openscad-studio.exe",
                scad_path
            ])


    def createGeometry(self, obj):
        print("create Geometry")    #def getSource(self):
        print("Do not process SCAD source on Document recompute")
        return

    #    print(f"Active Document {FreeCAD.ActiveDocument.Name}")
    #    #shp = shapeFromSourceFile(obj, keepWork, modules = obj.modules)
    #    shp = shapeFromSourceFile(obj, modules = obj.modules)
    #    print(f"Active Document {FreeCAD.ActiveDocument.Name}")
    #    if shp is not None:
    #        print(f"Initial Shape {obj.Shape}")
    #        print(f"Returned Shape {shp}")
    #        shp.check()
    #        newShp = shp.copy()
    #        print(f"New Shape {newShp}")
    #        print(f"Old Shape {shp}")
    #        #obj.Shape = shp.copy()
    #        obj.Shape = newShp
    #    else:
    #        print(f"Shape is None")

    def __getstate__(self):
        # Only persist what FreeCAD needs to reconstruct the proxy.
        # Transient runtime attributes must be excluded:
        #   _cached_shape  — Part.Shape/Compound, not JSON serializable
        #   _last_d_params — rebuilt by executeFunction on next run
        #   _executing     — runtime re-entrancy flag
        #   _initializing  — only meaningful during __init__
        #   Object         — FreeCAD re-injects this; storing it causes cycles
        _TRANSIENT = {"Object", "_cached_shape", "_cached_mesh", "_last_d_params",
                      "_executing", "_initializing", "_execute_count", "_execfn_count"}
        return {k: v for k, v in self.__dict__.items() if k not in _TRANSIENT}

    def __setstate__(self, state):
        self.__dict__.update(state)
        # Ensure transient attributes exist with safe defaults so execute()
        # and onChanged never raise AttributeError on a freshly restored proxy.
        self._cached_shape  = None
        self._cached_mesh   = None
        self._last_d_params = None
        self._executing     = False
        self._initializing  = False

class ViewSCADProvider:
    def __init__(self, obj):
        """Set this object to the proxy object of the actual view provider"""
        obj.Proxy = self


    def updateData(self, fp, prop):
        """If a property of the handled feature has changed we have the chance to handle this here"""
        pass

    def getDisplayModes(self, obj):
        """Return a list of display modes."""
        # print("getDisplayModes")
        modes = []
        modes.append("Shaded")
        modes.append("Wireframe")
        modes.append("Points")
        return modes


    def getDefaultDisplayMode(self):
        """Return the name of the default display mode. It must be defined in getDisplayModes."""
        return "Shaded"

    def setDisplayMode(self, mode):
        """Map the display mode defined in attach with those defined in getDisplayModes.\
               Since they have the same names nothing needs to be done. This method is optional"""
        return mode


    def onChanged(self, vp, prop):
        """Here we can do something when a single property got changed"""
        print(f"View Provider OnChanged : prop {prop}")


    def getIcon(self):
        """Return the icon in XPM format which will appear in the tree view. This method is\
               optional and if not defined a default icon is shown."""

    def __getstate__(self):
        """When saving the document this object gets stored using Python's json
        module.
        Since we have some un-serializable parts here -- the Coin stuff --
        we must define this method\
        to return a tuple of all serializable objects or None."""
        if hasattr(self, "Type"):  # If not saved just return
            return {"type": self.Type}
        else:
            pass

    def __setstate__(self, arg):
        """When restoring the serialized object from document we have the
        chance to set some internals here. Since no data were serialized
        nothing needs to be done here."""
        if arg is not None and arg != {}:
            if 'type' in arg:
                self.Type = arg["Type"]
            #print(self.Type)
        return None
