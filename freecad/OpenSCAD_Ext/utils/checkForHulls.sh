#!/usr/bin/env bash

# Usage: ./scan_scad_hull.sh /path/to/scad/dir
# If no path given, use current directory
ROOT_DIR="${1:-.}"
HULL_DIR="$ROOT_DIR/hull"

mkdir -p "$HULL_DIR"

# Find .scad files and search for hull(
find "$ROOT_DIR" -type f -name "*.scad" ! -path "$HULL_DIR/*" | while read -r file; do
    if grep -Eq '^[^/]*\bhull\s*\(' "$file"; then
        echo "Hull found: $file"
        cp -n "$file" "$HULL_DIR/"
    fi
done

echo "Done."

