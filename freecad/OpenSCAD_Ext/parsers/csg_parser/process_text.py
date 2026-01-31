import os
import shutil
import FreeCAD as App
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_utils import export_scad_str_to_dxf
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_utils import export_scad_str_to_svg
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_utils import diagnose_dxf

from freecad.OpenSCAD_Ext.core.OpenSCADdxf import importEZDXFshape

def process_text(node):
    return process_text_dxf(node)

def process_text_svg(node):
    """
    Convert OpenSCAD text() into a SVG via OpenSCAD,
    """

    # Build SCAD text command
    # params = scad_params_to_str(node.csg_params)
    # Use raw csg

    params = node.csg_params
    scad_str = f"text({params});"

    write_log("TEXT_UPDATE", f"Sending to OpenSCAD as SVG: {scad_str}")

    # OpenSCAD → DXF
    svg_path = export_scad_str_to_svg(scad_str, "output.svg")
    print(svg_path)

    # Problem FreeCAD only supports import of SVG as Document
    # Means using a temo document

    #try:
        #face = importEZDXFshape(
        #    filename=str(dxf_path),   # IMPORTANT: path only
        #    doc=App.ActiveDocument,
        #    inlayer=None,
        #    exlayer=None,
        #    retcompound=True
        #)
    #finally:
        # cleanup
    #    try:
    #        os.unlink(svg_path)
    #    except OSError:
    #        pass

    #    try:
    #       shutil.rmtree(tmp_dir)
    #    except OSError:
    #        pass

    #return face



def process_text_dxf(node):
    """
    Convert OpenSCAD text() into a DXF via OpenSCAD,
    then import using legacy DXF importer.
    """

    # Build SCAD text command
    # params = scad_params_to_str(node.csg_params)
    # Use raw csg

    params = node.csg_params
    scad_str = f"text({params});"

    write_log("TEXT_UPDATE", f"Sending to OpenSCAD as DXF: {scad_str}")

    # OpenSCAD → DXF
    dxf_path, tmp_dir = export_scad_str_to_dxf(scad_str, "output.dxf")
    diagnose_dxf(dxf_path)

    try:
        face = importEZDXFshape(
            filename=str(dxf_path),   # IMPORTANT: path only
            doc=App.ActiveDocument,
            inlayer=None,
            exlayer=None,
            retcompound=True
        )
    finally:
        # cleanup
        try:
            os.unlink(dxf_path)
        except OSError:
            pass

        try:
            shutil.rmtree(tmp_dir)
        except OSError:
            pass

    return face
