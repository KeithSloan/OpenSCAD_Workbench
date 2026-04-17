#2 Extract Variables

OpenSCAD Variables can exist in comments in a number of places

    * Start of file scad file.
        Examples 
            /Users/ksloan/github/CAD_Files_Git/OpenSCAD/Keyring Container v2.1.scad
    * Library Example

        * Developer_Notes
            - linear_bearings.scad

    * Before or After Module definitions
        Examples

#3 Export to FreeCAD

    * Options

        * VarSets
        * Vars extension
            - Frank David Martinez M - FreeCAD Vars extension
            - https://github.com/mnesarco/Vars
        * FreeCAD Spreadsheet
            The FreeCAD Spreadsheet has a number of Weakness


#3 FreeCAD OpenSCAD_Workbench - Preferences

    * Export Options
        - Prompt for export Option.
        - Selected option
            - VarSets
            - Vars
            - Spreadsheet

#3 When created
    * Create SCAD Object.
        - If variables exist at start of file.
        - For each Module in the scad file.

#3 For OpenSCAD Library Browser

    * Scan Modules | Select a Module | Create SCAD Module

    * Extract Variables Button

    Need to check if already exists in current Document

    OpenSCAD File Objects

 #3 Modules have Properties corresponding to OpenSCAD Module Variables.

    Can be referenced as follows
        * For Variable Set.
        * Variables Workbench 
        * Spreadsheet

    The following changes will cause re-evaluation of OpenSCAD Object Shape

        * Direct change of Property 
            Avoiding recalc on every keyboard click
            Maybe a change to OpenSCAD Feature Python? Extra property?
 
        * Change of Variable Set
        * Change of Variables
        * Change of Spreadsheet

 
    Export of the various FreeCAD variables to OpenSCAD

        * Andreas scad export

            - Variable Set
            - Variables
            - Spreadsheet 