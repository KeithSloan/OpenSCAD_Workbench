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

def create_scad_object(title, newFile, sourceFile, scadName="SCAD_Object"):
    write_log("Info",f"create scad object  ; newFile {newFile} scadName = {scadName} sourceFile = {sourceFile}")
    QtGui.QGuiApplication.setOverrideCursor(QtGui.Qt.ArrowCursor)
    dialog = OpenSCADeditOptions(scadName, sourceFile, newFile)
    result = dialog.exec_()
    QtGui.QGuiApplication.restoreOverrideCursor()
    if result != QtGui.QDialog.Accepted:
        pass
    write_log("Info",f"Action")
    options = dialog.getValues()
    write_log("Info",f"Options {options}") 

    # Create SCAD Object
    scadName = dialog.getName()
    sourceFile = dialog.get_sourceFile()
    scadObj = dialog.create_from_dialog(scadName)
    if scadObj:
        scadObj.editFile(sourceFile)

# Shared between SCADObject and SCADModule
def createMesh(srcObj, wrkSrc):
    print(f"Create Mesh {srcObj.Name} {wrkSrc}")
    try:
        tmpDir = tempfile.gettempdir()
        tmpOutFile = os.path.join(tmpDir, srcObj.Name+'.stl')
        print(f"Call OpenSCAD - Input file {wrkSrc} Output file {tmpOutFile}")
        tmpFileName=callopenscad(wrkSrc, \
            outputfilename=tmpOutFile, outputext='stl', \
            timeout=int(srcObj.timeout))
        if os.path.exists(tmpFileName): # If Timeout no file
            print(f"STL File name {tmpFileName}")
            mesh = Mesh.Mesh()
            print(f"files {tmpOutFile} {tmpFileName}")
            mesh.read(tmpFileName)
            #print(dir(mesh))
            print(f"Mesh bound box {mesh.BoundBox}")
            print(f"Count Facets {mesh.CountFacets}")
            #print(f"Facets {mesh.Facets}")
            print(f"Is Solid {mesh.isSolid()}")
            shape = Part.Shape()
            shape.makeShapeFromMesh(mesh.Topology, 0.1)
            return shape

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
def createBrep(srcObj, tmpDir, wrkSrc):
	from importAltCSG import  processCSG

	print(f"Create Brep {srcObj.scadName} {srcObj.fnmax}")
	actDoc = FreeCAD.activeDocument().Name
	print(f"Active Document {actDoc}")
	wrkDoc = FreeCAD.newDocument("work")
	try:
		print(f"Source : {srcObj.scadName}")
		print(f"SourceFile : {srcObj.sourceFile}")
		print(wrkDoc)
		csgOutFile = os.path.join(tmpDir, srcObj.Name+'.csg')
		# brepOutFile = os.path.join(tmpDir, srcObj.Name+'.brep')
		print("Call OpenSCAD to create csg file from scad")
		tmpFileName=callopenscad(wrkSrc, \
			outputfilename=csgOutFile, outputext='csg', \
			timeout=int(srcObj.timeout))
		if hasattr(srcObj, "source"):
			source = srcObj.scadName
		if hasattr(srcObj, "sourceFile"):
			source = srcObj.sourceFile
		global pathName    
		pathName = os.path.dirname(os.path.normpath(srcObj.scadName))
		print(f"Process CSG File name path {pathName} file {tmpFileName}")
		#processCSG(wrkDoc, pathName, tmpFileName, srcObj.fnmax)
		processCSG(wrkDoc, tmpFileName, srcObj.fnmax)
		# *** Does not work for earrings.scad
		shapes = []
		for cnt, obj in enumerate(wrkDoc.RootObjects, start=1):
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


def shapeFromSourceFile(srcObj, module=False, modules=False):
    global doc
    print(f"shapeFrom Source File : keepWork {srcObj.keep_work_doc}")
    tmpDir = tempfile.gettempdir()
    #if modules == True:
    #    wrkSrc = os.path.join(tmpDir, srcObj.Name+'.scad')
    #    #   wrkSrcFp = fopen(wrkSrc)
    #    #   scanForModules(wrkSrcFp, module)
    #else:
    #    wrkSrc = srcObj.sourceFile
    wrkSrc = srcObj.sourceFile

    print(f"source name {srcObj.Label} mode {srcObj.mode}")

    #srcObj.mode = "Mesh"

    if srcObj.mode == "Brep":
        brepShape = createBrep(srcObj, tmpDir, wrkSrc)
        print(f"Active Document {FreeCAD.ActiveDocument.Name}")
        return brepShape
        #return brepObj.Shape

    elif srcObj.mode == "Mesh":
        print(f"wrkSrc {wrkSrc}")
        return createMesh(srcObj, wrkSrc)
        #return createMesh(srcObj, tmpDir, wrkSrc)

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
                self.importType.addItem('Brep')
                self.importType.addItem('Opt')
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


class SCADfileBase:
    def __init__(self, obj, scadName, sourceFile, mode='Mesh', fnmax=16, timeout=30, keep=False):
        super().__init__()
        self.Object = obj      # ← REQUIRED in your case
        obj.addProperty("App::PropertyString","scadName","OpenSCAD","OpenSCAD scadObject")
        obj.scadName = scadName
        obj.setEditorMode("scadName",1)
        obj.addProperty("App::PropertyFile","sourceFile","OpenSCAD","OpenSCAD source")
        obj.sourceFile = sourceFile
        obj.addProperty("App::PropertyString","message","OpenSCAD","OpenSCAD message")
        obj.addProperty("App::PropertyBool","modules","OpenSCAD","OpenSCAD Uses Modules")
        obj.addProperty("App::PropertyBool","edit","OpenSCAD","Edit SCAD source")
        obj.addProperty("App::PropertyBool","execute","OpenSCAD","Process SCAD source")
        obj.modules = True
        obj.addProperty("App::PropertyEnumeration","mode","OpenSCAD","mode - create Brep or Mesh")
        modeLst = ['Mesh', 'Brep']
        modeIdx = modeLst.index(mode)
        obj.mode = modeLst
        obj.mode = modeIdx
        obj.addProperty("App::PropertyInteger","fnmax","OpenSCAD","Max Poylgon - If circle or cylinder has more than this number of sides, treat as circle or cyliner")
        obj.fnmax = fnmax
        obj.addProperty("App::PropertyBool","mesh_recombine","OpenSCAD","Mesh Recombine")
        obj.mesh_recombine = False
        obj.addProperty("App::PropertyBool","keep_work_doc","OpenSCAD","Keep FC Work Document")
        obj.keep_work_doc = keep
        obj.addProperty("App::PropertyInteger","timeout","OpenSCAD","OpenSCAD process timeout (secs)")
        obj.timeout = timeout
        obj.Proxy = self
        self.createGeometry(obj)

    def onChanged(self, fp, prop):
        print(f"{fp.Label} State : {fp.State} prop : {prop}")

        if "Restore" in fp.State:
            return

        if prop in ["Shape"]:
            print(f"OnChange Shape {fp.Shape}")
            return

        if prop in ['mode']:
                print(f"Change of Mode")

        if prop in ["execute"]:
            if fp.execute == True:
                self.executeFunction(fp)
                fp.execute = False
                FreeCADGui.SendMsgToActiveView("ViewFit")
            else:
                print(f"Touched execute Shape {fp.Shape}")
                #obj.Shape = self.newShape


        if prop in ["edit"]:
            if fp.edit == True:
                self.editFile(fp.sourceFile)
                fp.edit = False
            FreeCADGui.Selection.addSelection(fp)

        if prop in ["message"]:
            print("message changed")
            FreeCADGui.updateGui()


    def execute(self, fp):
        '''Do something when doing a recomputation, this method is mandatory'''
        print(f"execute")


    # use name render for new workbench
    # redirect for compatibility with old Alternate
    #
    def renderFunction(self, obj):
        write_log("Info","Render Function")
        self.executeFunction(obj)


    def executeFunction(self, obj):
        from timeit import default_timer as timer
        print(f"Execute {obj.Name} Mode {obj.mode} keepWork {obj.keep_work_doc}")
        start = timer()
        #print(dir(obj))
        obj.message = ""
        shp = shapeFromSourceFile(obj, modules = obj.modules)
        if shp is not None:
            print(f"Initial Shape {obj.Shape}")
            print(f"Returned Shape {shp}")
            #shp.check()
            #newShp = shp.copy()
            #print(f"New Shape {newShp}")
            #print(f"Old Shape {shp}")
            #obj.Shape = newShp
            obj.Shape = shp
        else:
            print(f"Shape is None")
            obj.Shape = Part.Shape()
        print(f"Function Object Shape {obj.Shape}")
        obj.execute = False
        #if obj.mode == 'Mesh':
        #    obj.ViewObject.DisplayMode = u"Wireframe"
        #if obj.mode == 'Brep':
        #    obj.ViewObject.DisplayMode = u"Shaded"
        obj.ViewObject.DisplayMode = u"Shaded"
        end = timer()
        print(f"==== Create Shape took {end-start} secs ====")    
        obj.recompute()
        #print(f"Active Document recompute {FreeCAD.ActiveDocument.Name}")
        #FreeCAD.ActiveDocument.recompute()
        FreeCADGui.Selection.addSelection(obj)
        FreeCADGui.runCommand('Std_RandomColor',0)
        FreeCADGui.SendMsgToActiveView("ViewFit")
        # Need to update Gui for properties change
        # try and catch as puts out warning
        try:
            obj.execute = False
            FreeCADGui.updateGui()
        except Exception as err:
            print(f"Warning {err}")
        #FreeCADGui.Selection.addSelection(obj)


    def editFunction(self):
        obj = self.Object

        if not hasattr(obj, "sourceFile"):
            FreeCAD.Console.PrintError("SCAD object has no sourceFile\n")
            return

        self.editFile(obj.sourceFile)


    def editFile(self, fname):  # For compatibility with legacy
        import FreeCAD
        import subprocess,  os, sys
        editorPathName = FreeCAD.ParamGet(\
            "User parameter:BaseApp/Preferences/Mod/OpenSCAD").GetString('externalEditor')
        print(f"Path to external editor {editorPathName}")
        # ToDo : Check pathname valid
        if editorPathName != "":
            p1 = subprocess.Popen( \
                [editorPathName, fname], \
                stdin=subprocess.PIPE,\
                stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    
        else:
            print(f"External Editor preference editorPathName not set")


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

"""def createSCADObject(title, createOption, objectName, filename):
    from PySide import QtGui
    from freecad.OpenSCAD_Ext.objects.menus_for_objects import SCADObject_Options
	#pathText = os.path.splitext(os.path.basename(filename))
	#objectName  = pathText[0]
    doc = FreeCAD.ActiveDocument
    if doc is None:
        doc = FreeCADGui.newDocument(objectName)

    QtGui.QGuiApplication.setOverrideCursor(QtGui.Qt.ArrowCursor)
    dialog = SCADObject_Options(title, objectName, createOption, parent=None)
    result = dialog.exec_()
    QtGui.QGuiApplication.restoreOverrideCursor()
    if result == QtGui.QDialog.Accepted:
        print(f" Action Result {dialog.result}")
        options = dialog.getValues()
        print(f"Options {options}")

		# Create SCAD Object
        # 
        obj = doc.addObject("Part::FeaturePython", objectName)
		#
		# SCADfileBase(obj, name, filename, mode='Mesh', fnmax=16, timeout=30)
        SCADfileBase(obj, \
			#os.path.splitext(os.path.basename(filename))[0],
            objectName, \
 			filename, \
			options[0], \
			options[1], \
			options[2])
		#print(dir(scadObj))
        write_log("Info","ViewSCADProvider")
        ViewSCADProvider(obj.ViewObject)
        if hasattr(obj, 'Proxy'):
            if hasattr(obj, "editFile"):
                obj.Proxy.editFile(filename)
            elif hasattr(obj, "executeFunc"):
                obj.Proxy.executeFunction(obj)
        return obj
"""
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
        return None

    def __setstate__(self, arg):
        """When restoring the serialized object from document we have the
        chance to set some internals here. Since no data were serialized
        nothing needs to be done here."""
        return None
