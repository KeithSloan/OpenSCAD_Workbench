"""
Display helpers for ScadFileType in Qt tree/list widgets.

Provides
--------
FILE_TYPE_LABELS  : dict mapping ScadFileType → human-readable label
                    (PURE_SCAD is shown as "Model" rather than "Pure SCAD")
FILE_TYPE_TIPS    : dict mapping ScadFileType → tooltip string
FILE_TYPE_COLOURS : dict mapping ScadFileType → hex colour string
DIR_COLOUR        : hex colour string for directory entries

get_file_type_icon(file_type) → QIcon
get_dir_icon()                → QIcon
get_file_type_color(file_type)→ QColor

Icons are built once from inline SVG and then cached.  The functions
return ``QIcon()`` / ``QColor()`` when Qt or SVG support is unavailable so
callers can use them unconditionally.
"""
from __future__ import annotations

from freecad.OpenSCAD_Ext.parsers.scadmeta import ScadFileType

try:
    from PySide.QtGui import QIcon, QPixmap, QColor
    from PySide.QtCore import QByteArray
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Human-readable labels
# ---------------------------------------------------------------------------

FILE_TYPE_LABELS: dict = {
    ScadFileType.PURE_SCAD:      "Model",        # produces geometry when rendered
    ScadFileType.LIBRARY:        "Library",       # include/use aggregator
    ScadFileType.VARIABLE:       "Config",        # only variable definitions
    ScadFileType.MODULES_ONLY:   "Modules",       # reusable module defs
    ScadFileType.FUNCTIONS_ONLY: "Functions",     # mathematical/utility functions
    ScadFileType.MIXED:          "Mixed",         # both modules and functions
    ScadFileType.UNKNOWN:        "Unknown",       # empty or unclassifiable
}

FILE_TYPE_TIPS: dict = {
    ScadFileType.PURE_SCAD:      "Model — produces 3D geometry when rendered directly",
    ScadFileType.LIBRARY:        "Library — include/use aggregator; no own geometry",
    ScadFileType.VARIABLE:       "Config — variable / constant definitions only",
    ScadFileType.MODULES_ONLY:   "Modules — reusable module definitions",
    ScadFileType.FUNCTIONS_ONLY: "Functions — mathematical or utility function definitions",
    ScadFileType.MIXED:          "Mixed — both module and function definitions",
    ScadFileType.UNKNOWN:        "Unknown — empty or unclassifiable SCAD file",
}

# Hex colour codes used for text in Qt widgets
FILE_TYPE_COLOURS: dict = {
    ScadFileType.PURE_SCAD:      "#27AE60",   # green  — runnable model
    ScadFileType.LIBRARY:        "#E67E22",   # orange — aggregator
    ScadFileType.VARIABLE:       "#E74C3C",   # red    — configuration
    ScadFileType.MODULES_ONLY:   "#2980B9",   # blue   — reusable modules
    ScadFileType.FUNCTIONS_ONLY: "#16A085",   # teal   — functions
    ScadFileType.MIXED:          "#8E44AD",   # purple — mixed content
    ScadFileType.UNKNOWN:        "#7F8C8D",   # grey   — unknown
}

DIR_COLOUR = "#B7950B"   # dark amber — directory


# ---------------------------------------------------------------------------
# Inline SVG icon data (16 × 16 px)
# ---------------------------------------------------------------------------
#
# Model      – green filled circle with white ▶ play triangle
#              (this file runs and produces output)
#
# Library    – three orange horizontal bars, darkening top→bottom
#              (layered include / aggregator stack)
#
# Config     – red rounded square with white "x=" label
#              (variable / constant data)
#
# Modules    – blue open square with "M" inside
#              (reusable building blocks)
#
# Functions  – teal circle with italic "f" inside
#              (mathematical function symbol)
#
# Mixed      – left half blue (M), right half teal (f) split tile
#              (contains both modules and functions)
#
# Unknown    – grey filled circle with white "?"
#
# Directory  – simple amber folder shape
# ---------------------------------------------------------------------------

_SVG: dict = {

    ScadFileType.PURE_SCAD: """\
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
  <circle cx="8" cy="8" r="7" fill="#27AE60"/>
  <polygon points="6,4 12,8 6,12" fill="white"/>
</svg>""",

    ScadFileType.LIBRARY: """\
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
  <rect x="2" y="3"  width="12" height="3" rx="1" fill="#E67E22"/>
  <rect x="2" y="7"  width="12" height="3" rx="1" fill="#CA6F1E"/>
  <rect x="2" y="11" width="12" height="3" rx="1" fill="#A04000"/>
</svg>""",

    ScadFileType.VARIABLE: """\
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
  <rect x="1" y="1" width="14" height="14" rx="2" fill="#E74C3C"/>
  <text x="8" y="12" font-family="monospace" font-size="9" font-weight="bold"
        text-anchor="middle" fill="white">x=</text>
</svg>""",

    ScadFileType.MODULES_ONLY: """\
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
  <rect x="1.5" y="1.5" width="13" height="13" rx="2"
        fill="none" stroke="#2980B9" stroke-width="2"/>
  <text x="8" y="12" font-family="sans-serif" font-size="10" font-weight="bold"
        text-anchor="middle" fill="#2980B9">M</text>
</svg>""",

    ScadFileType.FUNCTIONS_ONLY: """\
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
  <circle cx="8" cy="8" r="6.5" fill="none" stroke="#16A085" stroke-width="2"/>
  <text x="9" y="12.5" font-family="Georgia,serif" font-style="italic"
        font-size="12" font-weight="bold" text-anchor="middle" fill="#16A085">f</text>
</svg>""",

    ScadFileType.MIXED: """\
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
  <rect x="1" y="1" width="6"  height="14" rx="1" fill="#2980B9"/>
  <rect x="9" y="1" width="6"  height="14" rx="1" fill="#16A085"/>
  <text x="4"  y="12"   font-family="sans-serif" font-size="9"
        font-weight="bold" text-anchor="middle" fill="white">M</text>
  <text x="12" y="12.5" font-family="Georgia,serif" font-style="italic"
        font-size="11" text-anchor="middle" fill="white">f</text>
</svg>""",

    ScadFileType.UNKNOWN: """\
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
  <circle cx="8" cy="8" r="7" fill="#7F8C8D"/>
  <text x="8" y="13" font-family="sans-serif" font-size="13" font-weight="bold"
        text-anchor="middle" fill="white">?</text>
</svg>""",
}

_DIR_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
  <path d="M1,6 L1,13 Q1,14 2,14 L14,14 Q15,14 15,13 L15,6 Z" fill="#F39C12"/>
  <path d="M1,6 L1,5 Q1,4 2,4 L6,4 L7,6 Z" fill="#D68910"/>
</svg>"""


# ---------------------------------------------------------------------------
# Icon helpers
# ---------------------------------------------------------------------------

_icon_cache: dict = {}   # ScadFileType | "dir" -> QIcon


def _svg_to_icon(svg: str) -> "QIcon":
    """Render *svg* string to a QIcon; returns empty QIcon on any failure."""
    if not _QT_AVAILABLE:
        return QIcon() if _QT_AVAILABLE else None
    try:
        ba = QByteArray(svg.encode("utf-8"))
        pm = QPixmap()
        if pm.loadFromData(ba, "SVG"):
            return QIcon(pm)
    except Exception:
        pass
    return QIcon()


def get_file_type_icon(file_type: ScadFileType) -> "QIcon":
    """
    Return the 16×16 QIcon for *file_type*.

    Icons are created on first use and cached for subsequent calls.
    Returns an empty ``QIcon()`` when Qt is not available or the SVG
    cannot be rendered.
    """
    if not _QT_AVAILABLE:
        return None
    if file_type not in _icon_cache:
        svg = _SVG.get(file_type, "")
        _icon_cache[file_type] = _svg_to_icon(svg)
    return _icon_cache[file_type]


def get_dir_icon() -> "QIcon":
    """Return the folder QIcon for directory entries."""
    if not _QT_AVAILABLE:
        return None
    if "dir" not in _icon_cache:
        _icon_cache["dir"] = _svg_to_icon(_DIR_SVG)
    return _icon_cache["dir"]


def get_file_type_color(file_type: ScadFileType) -> "QColor":
    """Return the ``QColor`` for *file_type* text colouring."""
    if not _QT_AVAILABLE:
        return None
    return QColor(FILE_TYPE_COLOURS.get(file_type, "#7F8C8D"))
