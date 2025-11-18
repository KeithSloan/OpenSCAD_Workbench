import os

class OpenSCAD_Ext_Preferences:
    """Minimal stable preferences page."""

    def GetResources(self):
        base = os.path.dirname(__file__)
        form = os.path.join(base, "Resources", "ui", "preferences.ui")
        icon = os.path.join(base, "Resources", "Icons", "OpenSCAD_Ext.svg")
        return {
            "Pixmap": icon,
            "MenuText": "OpenSCAD_Ext Preferences",
            "ToolTip": "Set preferences for the OpenSCAD_Ext workbench",
            "Page": form,
        }

    def GetClassName(self):
        return "Gui::PrefPage"

