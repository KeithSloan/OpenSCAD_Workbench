# -*- coding: utf8 -*-
#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2012 Keith Sloan <keith@sloan-home.co.uk>               *
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
#*     Thanks to shoogen on the FreeCAD forum and Peter Li                 *
#*     for programming advice and some code.                               *
#*                                                                         *
#*                                                                         *
#***************************************************************************

from freecad.OpenSCAD_Ext.logger.Workbench_logger import *
printverbose = True

def checkObjShape(obj) :
    if printverbose: write_log("INFO",'Check Object Shape')
    if hasattr(obj, 'Shape'):    
        if obj.Shape.isNull() == True :
            if printverbose: write_log("INFO",'Shape is Null - recompute')
            obj.recompute()
        if (obj.Shape.isNull() == True):
            print(f'Recompute failed : {obj.Name}')
    else:
        if len(obj) > 0:
           print(f"check of obj list")
           for i in obj:
               checkObjShape(i)
        elif hasattr(obj, 'Proxy'):
           print(f"Proxy {obj.Proxy}")
        elif hasattr(obj, 'Name'):
            print(f"obj {obj.Name} has no Shape")
        else:
            print(f"obj {obj} has no Name & Shape")
            print(dir(obj[0]))

def checkAllChildShapes(children):
    write_log("INFO", "CheckAllChildShapes")
    for obj in children:
        checkObjShape(obj)
    write_log("INFO", "Re check ChildShapes")
    for obj in children:
        checkObjShape(obj)

def checkObjType2D(obj) :
    if obj.TypeId == 'Part::Part2DObject' :
       if printverbose: write_log("INFO",'2D')
       return True
    if obj.TypeId == 'Part::Cut' or obj.TypeId == 'Part::Fuse' or \
       obj.TypeId == 'Part::Common' or obj.TypeId == 'Part::MultiFuse' :
       if checkObjType2D(obj.Base) and checkObjType2D(obj.Tool) :
          return True
    return  False

def planeFromNormalPoints(a,b) :
    #dir = FreeCAD.Vector(a[0]-b[0], a[1]-b[1], a[2]-b[2])
    d3 = FreeCAD.Vector(1/(a[0]-b[0]), 1/(a[1]-b[1]), 1/(a[2]-b[2]))
    print('a cross b : '+str(a.cross(b)))
    #d2 = a.cross(b)
    #d2 = FreeCAD.Vector(0.0, 0.0, 1.0)
    #d2 = FreeCAD.Vector(1.0,0.0,0.0)
    d2 = FreeCAD.Vector(0.0,1.0,0.0)
    print('d2 : '+str(d2))
    return Part.makePlane(200,50,a,d2) 

