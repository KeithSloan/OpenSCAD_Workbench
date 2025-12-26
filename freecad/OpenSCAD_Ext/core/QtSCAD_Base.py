#***************************************************************************
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
__title__="FreeCAD OpenSCAD Workbench "
__author__ = "Keith Sloan <keith@sloan-home.co.uk>"
__url__ = ["http://www.sloan-home.co.uk/ImportSCAD"]

import FreeCAD, FreeCADGui, os
if FreeCAD.GuiUp:
    import FreeCADGui
    gui = True
else:
    print("FreeCAD Gui not present.")
    gui = False

# Save the native open function to avoid collisions
if open.__module__ in ['__builtin__', 'io']:
    pythonopen = open

from PySide import QtGui, QtCore


params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD")
printverbose = params.GetBool('printverbose',False)
print(f'Verbose = {printverbose}')

class ShapeType(QtGui.QWidget):
	def __init__(self):
		super().__init__()
		self.layout = QtGui.QHBoxLayout()
		self.label = QtGui.QLabel('Import Type')
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


from PySide import QtGui, QtCore

class SCADObject_Options(QtGui.QDialog):
	def __init__(self, title, objectName, createOption=False, parent=None):
		super().__init__(parent)

		self.createOption = createOption
		self.objectName = objectName
		self.result = None

		self.initUI(title)

	def initUI(self, title):
		# Window settings
		self.setGeometry(150, 250, 300, 300)
		self.setWindowTitle(title)
		self.setMouseTracking(True)

		# Main layout
		self.layout = QtGui.QVBoxLayout()
		self.setLayout(self.layout)

		# Dialog buttons
		self.buttonBox = QtGui.QDialogButtonBox(
		QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel,
        	self
    		)
		#Connect the dialog buttons to standard slots
		self.buttonBox.accepted.connect(self.accept)
		self.buttonBox.rejected.connect(self.reject)
		if self.createOption :
			self.createOnly = BooleanValue('Create Only (Edit)',True)
			self.layout.addWidget(self.createOnly)
		self.shapeType = ShapeType()
		self.layout.addWidget(self.shapeType)
		self.fnMax = IntegerValue('FnMax', 16)
		self.layout.addWidget(self.fnMax)
		self.timeOut = IntegerValue('TimeOut', 30)
		self.layout.addWidget(self.timeOut)
		self.keepOption = BooleanValue("Keep File",False)
		self.layout.addWidget(self.keepOption)
		self.layout.addWidget(self.buttonBox)
		self.setLayout(self.layout)
		self.show()

	def getValues(self):
		return(
			self.shapeType.getVal(), \
			self.fnMax.getVal(), \
			self.timeOut.getVal(), \
			self.keepOption.getVal()
			)

	def getCreateOption(self):
		# Tuple of optionSet and value
		return ( self.createOption, self.createOnly.getVal() )

	def onCancel(self):
		self.result = 'cancel'
		#QtGui.QGuiApplication.restoreOverrideCursor()

	def onOk(self):
		self.result = 'ok'
		#QtGui.QGuiApplication.restoreOverrideCursor()	

