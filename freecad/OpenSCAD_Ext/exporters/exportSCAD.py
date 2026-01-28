# Dev wrapper to prevent import for exportSCAD from being cached

import importlib
from ..exporters import exportSCAD_wrapped

def export(*args, **kwargs):
    importlib.reload(exportSCAD_wrapped)
    return exportSCAD_wrapped.export(*args, **kwargs)
