#!/bin/bash
# gen_hull_csgs.sh
#
# Batch-generate .csg from the OpenFlexure hull .scad files using the OpenSCAD
# CLI.  Two purposes:
#   1. Verify the .scad fixes — if OpenSCAD emits a CSG, the includes resolve
#      and the top-level call renders.  EMPTY/FAIL flags the ones still broken.
#   2. Produce a .csg corpus so the importer can be tested directly on .csg
#      (fast: no per-file OpenSCAD round-trip, no customizer dialogs).
#
# CSG export (-o file.csg) only writes the CSG tree — it does NOT run CGAL, so
# it's quick even for complex models.
#
# Usage:
#   bash gen_hull_csgs.sh
#   OPENSCAD=/path/to/OpenSCAD bash gen_hull_csgs.sh    # override the binary
#   SRC=/some/dir OUT=/some/out bash gen_hull_csgs.sh   # override in/out dirs

set -u

SRC="${SRC:-/Users/ksloan/Documents/OpenSCAD/libraries/openflexure/hull}"
OUT="${OUT:-/Users/ksloan/Workbenches/OpenSCAD_Workbench/testcases/Hull_Tests/openflexure_csg}"

find_openscad() {
  if [ -n "${OPENSCAD:-}" ] && [ -x "${OPENSCAD:-}" ]; then printf '%s' "$OPENSCAD"; return 0; fi
  local cands=(
    "/Applications/OpenSCAD-2025.3.10.app/Contents/MacOS/OpenSCAD"
    "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
    "/Applications/OpenSCAD-2021.01.app/Contents/MacOS/OpenSCAD"
  )
  local c
  for c in "${cands[@]}"; do [ -x "$c" ] && { printf '%s' "$c"; return 0; }; done
  local a b
  for a in /Applications/OpenSCAD*.app; do
    b="$a/Contents/MacOS/OpenSCAD"
    [ -x "$b" ] && { printf '%s' "$b"; return 0; }
  done
  command -v openscad 2>/dev/null
}

OSCAD="$(find_openscad)"
if [ -z "$OSCAD" ]; then
  echo "ERROR: OpenSCAD CLI not found. Re-run as: OPENSCAD=/full/path/to/OpenSCAD bash $0"
  exit 1
fi
echo "Using OpenSCAD : $OSCAD"
echo "Source         : $SRC"
echo "Output         : $OUT"
echo

mkdir -p "$OUT"
LOG="$OUT/_gen.log"; : > "$LOG"

pass=0; empty=0; fail=0
shopt -s nullglob
for f in "$SRC"/*.scad; do
  name="$(basename "${f%.scad}")"
  out="$OUT/$name.csg"
  if err="$("$OSCAD" -o "$out" "$f" 2>&1)"; then
    sz=$( [ -f "$out" ] && wc -c < "$out" || echo 0 )
    # An empty OpenSCAD CSG is a 1-byte file (just a newline); treat tiny as empty.
    if [ "${sz:-0}" -gt 16 ]; then
      printf 'PASS   %s  (%s bytes)\n' "$name" "$sz"; pass=$((pass+1))
    else
      printf 'EMPTY  %s  (rendered nothing — check top-level call)\n' "$name"; empty=$((empty+1))
      printf '[%s] EMPTY\n%s\n\n' "$name" "$err" >> "$LOG"
    fi
  else
    printf 'FAIL   %s\n' "$name"; fail=$((fail+1))
    printf '[%s] FAIL\n%s\n\n' "$name" "$err" >> "$LOG"
  fi
done

echo
echo "==== $pass pass, $empty empty, $fail fail ===="
echo "CSGs in : $OUT"
echo "Errors  : $LOG"
