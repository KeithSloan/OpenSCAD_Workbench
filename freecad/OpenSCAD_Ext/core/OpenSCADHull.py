import FreeCAD, FreeCADGui, Part

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.core.checkObjectShapes import *
from freecad.OpenSCAD_Ext.core.openSCAD_brepHull import create_Brep_Hull_Shape

from FreeCAD import Units
from pivy import coin

printverbose = False

class HullClassFeature:
    def __init__(self, obj, objList):
        obj.addExtension("App::GeoFeatureGroupExtensionPython")
        #obj.addExtension("App::PartExtensionPython")
        obj.Proxy = self

        if objList:
            obj.Group = objList

    def execute(self, obj):
        if not obj.Group or len(obj.Group) < 2:
            return
        obj.Shape = createHullShape(obj.Group)

class ViewProviderHull:
    def __init__(self, vobj=None):
        self.ViewObject = None
        if vobj:
            vobj.Proxy = self

    def attach(self, vobj):
        vobj.addExtension("Gui::ViewProviderGeoFeatureGroupExtensionPython")
        self.ViewObject = vobj

    def claimChildren(self):
        return self.ViewObject.Object.Group

    def getDefaultDisplayMode(self):
        return "Flat Lines"

    def __getstate__(self):
        return None

    def __setstate__(self, _state):
        return None

class ViewProviderMyGroupEx(ViewProviderHull):
    def __init__(self, vobj=None):
        self.group_node = None
        super().__init__(vobj)

    def attach(self, vobj):
        super().attach(vobj)
        self.setupShapeGroup()

    def setupShapeGroup(self):
        vobj = self.ViewObject
        if getattr(self, 'group_node', None) or \
                vobj.SwitchNode.getNumChildren() < 2:
            return
        self.group_node = vobj.SwitchNode.getChild(0)
        for i in range(1, vobj.SwitchNode.getNumChildren()):
            node = coin.SoSeparator()
            node.addChild(self.group_node)
            node.addChild(vobj.SwitchNode.getChild(i))
            vobj.SwitchNode.replaceChild(i,node)

    def getDetailPath(self,subname,path,append):
        if not subname or not getattr(self, 'group_node', None):
            raise NotImplementedError
        subs = Part.splitSubname(subname)
        objs = subs[0].split('.')

        vobj = self.ViewObject
        mode = vobj.SwitchNode.whichChild.getValue()
        if mode <= 0:
            raise NotImplementedError

        if append:
            path.append(vobj.RootNode)
            path.append(vobj.SwitchNode)

        node = vobj.SwitchNode.getChild(mode);
        path.append(node)
        if mode > 0:
            if not objs[0]:
                path.append(node.getChild(1))
            else:
                path.append(node.getChild(0))
        if not objs[0]:
            return vobj.getDetailPath(subname,path,False)

        for child in vobj.claimChildren():
            if child.Name == objs[0]:
                sub = Part.joinSubname('.'.join(objs[1:]),subs[1],subs[2])
                return child.ViewObject.getDetailPath(sub,path,True)

    def getElementPicked(self,pp):
        if not getattr(self, 'group_node', None):
            raise NotImplementedError
        vobj = self.ViewObject
        path = pp.getPath()
        if path.findNode(self.group_node) < 0:
            raise NotImplementedError
        for child in vobj.claimChildren():
            if path.findNode(child.ViewObject.RootNode) < 0:
                continue
            return child.Name + '.' + child.ViewObject.getElementPicked(pp)

    def onChanged(self,_vobj,prop):
        if prop == 'DisplayMode':
            self.setupShapeGroup()

def checkGroupShapes(groupList):
    # Objects on Parser stake may none be rendered
    # Check objects rendered i.e. if null drive recomopute
    print("Check Group Shapes")
    for i in groupList:
        checkObjShape(i)


def createHullShape(groupList):

    # Try for Breo version of Hull Shaoe
    retShape = create_Brep_Hull_Shape(groupList)
    if retShape is None:
        write_log("Info", "Process OpenSCAD Shapes via OpenSCAD")

        #from OpenSCADFeatures import CGALFeature
        #myObj = FreeCAD.ActiveDocument.addObject('Part::FeaturePython','Fred')
        #CGALFeature(myObj,'hull',obj.Group)
        # import OpenSCADFeatures
        #return myObj.Shape
        retShape = process_ObjectsViaOpenSCADShape(FreeCAD.ActiveDocument, groupList,'hull',maxmeshpoints=None)
        write_log("Info",f"Return Shape {retShape}")

    return retShape

#def makeHullObject(List, ex=False):
#    print(f"makeHullObject {List} length {len(List)}")
#    if len(List) == 1:
#       print(f"List of Single Parts TypeId {List[0].TypeId}")
#       if List[0].TypeId == "MultFuse":
#          if hasattr(List[0], "Shapes"):
#             print(f"Expand MultiFuse to List of Shapes length {len(List)}")
#             return makeHullObject(List[0].Shapes)
             

def deFuseListGroup(listGroup):
    ##########################################################
    # List could be a list of Parts or a single MultiFuse Part
    ##########################################################
    if len(listGroup) == 1:
       if listGroup[0].TypeId == "Part::MultiFuse":
          write_log("Info",f"MultiFuse {listGroup.Label}")
          return listGroup[0].Shapes
    return listgroup

def makeHullObject(listGroup, ex=False):
    doc = FreeCAD.ActiveDocument
    if not doc:
        doc = FreeCAD.newDocument()

    objList = deFuseListGroup(listGroup)
    #hullObj = doc.addObject("App::DocumentObjectGroupPython", "Hull")
    hullObj = doc.addObject("Part::FeaturePython", "Hull")
    if ex:
        ViewProviderMyGroupEx(hullObj.ViewObject)
    else:
        ViewProviderHull(hullObj.ViewObject)
    HullClassFeature(hullObj, objList)

    doc.recompute()
    return hullObj