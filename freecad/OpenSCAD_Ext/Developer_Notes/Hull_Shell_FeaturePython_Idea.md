# Design idea — retain constituent shapes, operate on the outer shell

Status: **idea / not implemented.** Recorded for future work.

## The idea

When the importer builds a shape from several primitives (e.g. a
`linear_extrude` of `union(circle, circle, square)`), it currently **fuses**
everything into one B-Rep solid and then throws the constituent structure away.
Downstream operations (booleans, hulls) then have to reverse-engineer that
structure (e.g. extract silhouettes off the fused solid) — which is exactly
where the hull loft struggles.

Instead: represent such a shape as a **`Part::FeaturePython`** object (similar to
a Part *Compound* / *MultiPart*) that **keeps the constituent sub-shapes**
(the circles + the square, the individual primitives) as hidden children, while
presenting an **outer shell** as its public `Shape`.

The key property the user wants:

> **Subsequent operations can just work on the outer shell** — booleans, hulls,
> etc. operate on the simple outer boundary, not on the internal seams between
> the fused primitives.

## Why it helps

- **Hull at the primitive level.** With the constituents retained, a `hull()`
  can be computed analytically on the *simple* parts (e.g. hull the 2-D
  primitives → extrude/loft) instead of extracting silhouettes from a complex
  fused solid. This sidesteps the single-loft / silhouette problems for cases
  like the `compact_nut_seat` extrudes (part-circle + part-square ends).
- **Cleaner outer shell for booleans.** Operating on the outer shell avoids the
  internal coplanar seams left by fusing primitives, which otherwise confuse
  OCC booleans and silhouette extraction.
- **Keeps CSG provenance.** Retaining the primitive structure is aligned with
  staying close to the OpenSCAD CSG tree rather than collapsing to B-Rep early.

## Sketch of the approach (to flesh out later)

1. A `Part::FeaturePython` proxy that stores the list of constituent
   shapes/primitives (with their placements) plus a computed outer-shell
   `Shape`.
2. `execute()` builds the outer shell (fuse → `removeSplitter` → keep only the
   outer boundary; or keep the union shell).
3. View provider hides the sub-shapes; only the outer shell is selectable for
   downstream ops.
4. Hull/boolean handlers check for this type and, when present, use the retained
   primitives (analytical path) and/or the clean outer shell.

## Relationship to the hull roadmap

This is a **deeper / orthogonal** direction to the loft work in
`BrepHullLofts_Architecture.md` (single-loft → option 1 piecewise sub-wire lofts
→ option 2 multi-patch tangent). The axis fix (using the longest combined-bbox
dimension when centres of mass are concentric) already removed the immediate
`compact_nut_seat` first-hull failure; this idea is a larger restructuring to
pursue if the silhouette-based loft keeps hitting walls on complex fused inputs.
