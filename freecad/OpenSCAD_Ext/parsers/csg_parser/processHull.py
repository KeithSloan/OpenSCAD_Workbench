import FreeCAD
from FreeCAD import Vector, Matrix
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_spheres import hull_spheres
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_cylinders import hull_cylinders_cones
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_cubes import hull_cubes


# Dev instrumentation.  While True, the hull dispatch trace is mirrored to the
# FreeCAD Report View; everything is always written to workbench.log regardless.
# Set False before merging to main (Report View policy: silent normal ops).
HULL_DEBUG = True


def _dbg(msg):
    """Log to file always; mirror to the Report View while HULL_DEBUG is on."""
    write_log("Hull", msg)
    if HULL_DEBUG:
        FreeCAD.Console.PrintMessage(f"[HULL] {msg}\n")


_loft_fail_count = 0


def _export_failed_loft(shapes):
    """Save the input shapes of a failed BRep hull loft as .brep files in the
    same directory as the CSG being imported, for offline inspection.

    Files: <csg-stem>_loftfail_<n>_A.brep, _B.brep, and _info.txt (placement /
    bbox / validity).  No-op if the CSG directory is unknown (e.g. .scad imports
    processed from a temp file) or fewer than 2 shapes were involved.
    """
    global _loft_fail_count
    if not shapes or len(shapes) < 2:
        return
    try:
        import os
        from freecad.OpenSCAD_Ext.parsers.csg_parser import processAST as _pa
        outdir = getattr(_pa, "_current_csg_dir", None)
        stem = getattr(_pa, "_current_csg_stem", None) or "model"
        if not outdir or not os.path.isdir(outdir):
            _dbg("  failed-loft export skipped (CSG directory unknown)")
            return
        _loft_fail_count += 1
        n = _loft_fail_count
        info = []
        for tag, s in zip(("A", "B"), shapes[:2]):
            fn = os.path.join(outdir, f"{stem}_loftfail_{n}_{tag}.brep")
            try:
                s.exportBrep(fn)
                info.append(
                    f"{tag}: {os.path.basename(fn)}  type={s.ShapeType} "
                    f"solids={len(s.Solids)} faces={len(s.Faces)} "
                    f"vol={getattr(s, 'Volume', 0):.3f} valid={s.isValid()} "
                    f"closed={s.isClosed()}\n   Placement={s.Placement}\n"
                    f"   BoundBox={s.BoundBox}")
            except Exception as e:
                info.append(f"{tag}: export failed: {e}")
        with open(os.path.join(outdir, f"{stem}_loftfail_{n}_info.txt"), "w") as f:
            f.write("\n".join(info) + "\n")
        _dbg(f"  saved failed-loft shapes → {stem}_loftfail_{n}_A/B.brep (next to CSG)")
    except Exception as ex:
        _dbg(f"  failed-loft export error: {ex}")


def _warn(msg):
    """Write a hull-fallback reason to the log file only.

    Hull fallbacks are normal — the parent boolean node detects _fallback_used
    and escalates to a whole-node OpenSCAD call, which importASTCSG then
    surfaces to the user as a single summary PrintWarning.  Per-hull orange
    panel noise is redundant and confusing.

    Use FreeCAD.Console.PrintError directly (not _warn) if geometry is
    genuinely lost with no recovery path.
    """
    write_log("Hull", msg)


# -----------------------------
# Public API
# -----------------------------
def try_hull(node):
    write_log("AST", f"Try Hull node_type={node.node_type}")

    if node.node_type != "hull":
        return None

    child_summary = ", ".join(
        f"{c.node_type}({len(c.children or [])})" for c in (node.children or [])
    )
    write_log("Hull", f"Hull children ({len(node.children or [])}): [{child_summary}]")

    # ── Tolerant collection: primitives from AST + shapes from complex children ─
    from freecad.OpenSCAD_Ext.parsers.csg_parser.processAST import process_AST_node

    primitives = []
    matrices = []
    shapes = []

    def _extract_shape(result):
        """Extract a Part.Shape from a process_AST_node return value."""
        if result is None:
            return
        items = result if isinstance(result, list) else [result]
        for item in items:
            if isinstance(item, tuple) and len(item) >= 2:
                s, pl = item[0], item[1]
            else:
                s, pl = item, None
            if s is not None:
                s = s.Shape if hasattr(s, 'Shape') else s
                if pl is not None and hasattr(pl, 'Matrix'):
                    s = s.copy()
                    s.transformShape(pl.Matrix)
                if hasattr(s, 'BoundBox'):
                    shapes.append(s)

    def _descend(children, parent_matrix=None):
        """Walk hull children: collect simple primitives, descend into the rest.

        Transparent wrappers (group, color, multmatrix) and unions are
        flattened: hull(A ∪ B, …) ≡ hull(A, B, …), so a union contributes its
        members directly, exactly like a nested hull.  This keeps the analytical
        primitive path (Path 1) available and avoids the lone-union case that
        would otherwise produce a single fused shape and fall back to OpenSCAD.

        Intersection is approximated by its first primitive child, since
        hull(A ∩ B, …) ⊆ hull(A, …).  Any other op (difference, minkowski,
        extrude, offset, …) is fully evaluated to a BRep shape and hulled via
        the shape-based path.
        """
        for child in (children or []):
            matrix = (
                parent_matrix.multiply(child.matrix)
                if (parent_matrix and hasattr(child, "matrix"))
                else (child.matrix if hasattr(child, "matrix") else parent_matrix)
            )
            nt = child.node_type

            if nt in ("group", "color"):
                _descend(child.children, matrix)

            elif nt == "multmatrix":
                if hasattr(child, "matrix"):
                    _descend(child.children, matrix)
                else:
                    _descend(child.children, parent_matrix)

            elif nt in ("hull", "union"):
                write_log("Hull",
                    f"Flattening {nt} — {len(child.children or [])} children")
                _descend(child.children, matrix)

            elif nt in ("sphere", "cube", "cylinder",
                        "circle", "square", "polygon"):
                primitives.append(child)
                matrices.append(matrix if matrix else Matrix())

            elif nt == "intersection":
                found = False
                for sub in (child.children or []):
                    if sub.node_type in ("sphere", "cube", "cylinder"):
                        primitives.append(sub)
                        matrices.append(matrix if matrix else Matrix())
                        found = True
                        break
                if not found:
                    _dbg("intersection: no usable primitive, creating shape")
                    try:
                        _extract_shape(process_AST_node(child))
                    except Exception as ex:
                        _dbg(f"  intersection shape failed: {ex}")

            else:
                # Complex op: difference, minkowski, extrude, offset, …
                _dbg(f"Descending into '{nt}' — creating child shape")
                try:
                    n_before = len(shapes)
                    _extract_shape(process_AST_node(child))
                    if len(shapes) == n_before:
                        _dbg(f"  '{nt}' produced no shape")
                except Exception as ex:
                    _dbg(f"  '{nt}' shape failed: {ex}")

    _descend(node.children)

    _dbg(f"Collected: {len(primitives)} primitives, {len(shapes)} complex shapes")

    # ── Path 1: AST-based dispatch (only when ALL children are simple) ─
    if len(primitives) >= 2 and len(shapes) == 0:
        geo = normalize_primitives(primitives, matrices)
        if geo is not None:
            _dbg(f"Path 1: AST dispatch with {len(geo)} primitive(s)")
            try:
                result = try_hull_dispatch(geo)
            except Exception as ex:
                # An analytical handler must never abort the whole import —
                # fall through to the shape-based path on any failure.
                _dbg(f"Path 1: dispatch raised ({ex}) — falling through")
                result = None
            if result is not None:
                _dbg("Path 1: AST dispatch OK")
                return result
            _dbg("Path 1: AST dispatch returned None")

    # ── Convert primitives to shapes if needed ────────────────────────
    all_shapes = list(shapes)
    if len(all_shapes) < 2:
        for child, mat in zip(primitives, matrices):
            try:
                r = process_AST_node(child)
                # Apply the accumulated transform matrix to each shape.
                items = r if isinstance(r, list) else [r]
                for item in items:
                    if isinstance(item, tuple) and len(item) >= 2:
                        s, pl = item[0], item[1]
                    else:
                        s, pl = item, None
                    if s is not None:
                        s = s.Shape if hasattr(s, 'Shape') else s
                        # Combine child's own placement with accumulated matrix.
                        if pl is not None and hasattr(pl, 'Matrix'):
                            s = s.copy()
                            s.transformShape(pl.Matrix)
                        if mat is not None:
                            s = s.copy()
                            s.transformShape(mat)
                        if hasattr(s, 'BoundBox'):
                            all_shapes.append(s)
            except Exception as ex:
                write_log("Hull", f"  primitive->shape failed: {ex}")

    _dbg(f"Path 2: shape-based with {len(all_shapes)} total shape(s)")

    # ── Single child: hull(X) is just the convex hull of X ────────────
    # OpenSCAD allows hull() with one child (often the result of mirror/
    # translate wrappers around a single primitive).  A lone convex primitive
    # (cylinder/cube/sphere) IS its own hull → return it unchanged (smooth, no
    # faceting).  A lone complex shape may be concave, so take its convex hull.
    if len(all_shapes) == 1:
        if len(shapes) == 0 and len(primitives) == 1:
            _dbg("hull of a single primitive → returning it unchanged")
            return all_shapes[0]
        _dbg("hull of a single complex shape → convex hull")
        try:
            from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_brep import (
                hull_brep_shapes
            )
            result = hull_brep_shapes(all_shapes)
            if result is not None:
                return result
        except Exception as ex:
            _dbg(f"  single-shape convex hull err: {ex}")
        return all_shapes[0]

    if len(all_shapes) >= 2:
        from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_mixed_curve import (
            hull_sphere_polyhedron
        )
        from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_brep import (
            hull_brep_shapes
        )
        import Part as _Part

        # A shape is a "sphere" for hull_sphere_polyhedron only if it IS a full
        # sphere (a single spherical face) — NOT merely any solid that happens to
        # contain a spherical face (e.g. a clipped sphere from a difference, which
        # has sphere + plane faces).  The latter must take the loft/faceted path.
        spheres, polys = [], []
        for s in all_shapes:
            try:
                faces = s.Faces
                if len(faces) == 1 and isinstance(faces[0].Surface, _Part.Sphere):
                    spheres.append(s)
                else:
                    polys.append(s)
            except Exception:
                polys.append(s)

        # ── Analytical: sphere + polyhedron ──────────────────────────
        _dbg(f"  classified: spheres={len(spheres)} polys={len(polys)}")

        for sp in spheres:
            for po in polys:
                try:
                    result = hull_sphere_polyhedron(sp, po)
                    if result is not None:
                        _dbg("  sphere+poly analytical OK")
                        return result
                except Exception as ex:
                    _dbg(f"  sphere+poly err: {ex}")

        # ── General silhouette + loft (smooth BRep) ──────────────────
        loft_result = None
        if len(all_shapes) == 2:
            from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_brep_loft import (
                hull_brep_loft
            )
            _dbg("  trying brep loft (2 shapes)")
            try:
                loft_result = hull_brep_loft(all_shapes)
            except Exception as ex:
                _dbg(f"  brep loft err: {ex}")
                loft_result = None
            if loft_result is None:
                _export_failed_loft(all_shapes)

        # ── Faceted convex hull: always geometrically correct ─────────
        # Computed both as the fallback AND as a yardstick to validate the loft.
        # A loft can report "OK" yet be twisted/self-intersecting (wrong vertex
        # correspondence), which then corrupts downstream OCC booleans.  Accept
        # the smooth loft ONLY when its volume matches the faceted hull and it is
        # a valid solid; otherwise use the faceted hull.
        faceted = None
        try:
            faceted = hull_brep_shapes(all_shapes)
        except Exception as ex:
            _dbg(f"  general BRep err: {ex}")

        if loft_result is not None:
            accept = False
            try:
                if faceted is not None and faceted.Volume > 1e-9:
                    rel = abs(loft_result.Volume - faceted.Volume) / faceted.Volume
                    accept = (rel < 0.05) and loft_result.isValid()
                    _dbg(f"  loft vol={loft_result.Volume:.1f} "
                         f"faceted={faceted.Volume:.1f} rel={rel:.3f} "
                         f"valid={loft_result.isValid()} -> "
                         f"{'ACCEPT loft' if accept else 'REJECT loft -> faceted'}")
                else:
                    accept = bool(loft_result.isValid())  # no yardstick — accept if valid
            except Exception:
                accept = False
            if accept:
                return loft_result

        if faceted is not None:
            _dbg("  using faceted BRep")
            return faceted

    _dbg("hull: no native path succeeded → returning None")
    return None


def normalize_primitives(primitives, matrices):
    out = []

    for node, mat in zip(primitives, matrices):
        pos = Vector(0, 0, 0)
        axis = Vector(0, 0, 1)

        if mat:
            pos = mat.multVec(pos)
            axis = mat.multVec(axis) - mat.multVec(Vector(0, 0, 0))

        if node.node_type == "sphere":
            if "r" not in node.params:
                return None
            out.append({
                "type": "sphere",
                "center": pos,
                "r": node.params["r"],
            })

        elif node.node_type == "cube":
            if "size" not in node.params:
                return None
            size_val = node.params["size"]
            if isinstance(size_val, (list, tuple)):
                sx, sy, sz = float(size_val[0]), float(size_val[1]), float(size_val[2])
            else:
                sx = sy = sz = float(size_val)
            center_flag = bool(node.params.get("center", False))
            # Compute the Part.makeBox corner in world space.
            # pos = mat.multVec(0,0,0) = world position of the cube's local origin.
            # center=false: local origin IS the corner.
            # center=true:  local origin IS the geometric centre; corner is at
            #               (-sx/2, -sy/2, -sz/2) in local space.
            if center_flag:
                if mat:
                    corner = mat.multVec(Vector(-sx / 2, -sy / 2, -sz / 2))
                else:
                    corner = Vector(-sx / 2, -sy / 2, -sz / 2)
            else:
                corner = pos  # pos already equals mat.multVec(0,0,0) = corner
            # Geometric centre (used by hull_cubes bbox logic)
            geom_center = corner + Vector(sx / 2, sy / 2, sz / 2)
            out.append({
                "type": "cube",
                "center": geom_center,  # geometric centre, always correct
                "corner": corner,       # Part.makeBox origin, always correct
                "size": [sx, sy, sz],
            })

        elif node.node_type == "cylinder":
            params = node.params

            if "h" not in params:
                return None
            h = float(params["h"])

            # --- Radius precedence (OpenSCAD rules) ---
            if "r" in params:
                r1 = r2 = float(params["r"])
            elif "r1" in params or "r2" in params:
                r1 = float(params.get("r1", 0))
                r2 = float(params.get("r2", 0))
            elif "d" in params:
                r1 = r2 = float(params["d"]) / 2.0
            elif "d1" in params or "d2" in params:
                r1 = float(params.get("d1", 0)) / 2.0
                r2 = float(params.get("d2", 0)) / 2.0
            else:
                return None

            if r1 < 0 or r2 < 0:
                return None

            # ---------------------------------------
            # Axis and base from transform
            # ---------------------------------------
            base = Vector(0, 0, 0)
            axis_vec = Vector(0, 0, 1)

            if mat:
                base = mat.multVec(base)
                axis_end = mat.multVec(Vector(0, 0, 1))
                axis_vec = axis_end - base

            if axis_vec.Length == 0:
                return None

            # ALWAYS convert to unit direction
            axis_vec = axis_vec / axis_vec.Length

            # ---------------------------------------
            # Center handling
            # ---------------------------------------
            center_flag = bool(params.get("center", False))

            if h < 0:
                h = abs(h)
                axis_vec = axis_vec * -1

            if center_flag:
                base = base - axis_vec * (h / 2.0)

            center = base + axis_vec * (h / 2.0)

            # ---------------------------------------
            # Store canonical representation
            # ---------------------------------------
            out.append({
                "type": "cylinder",   # keep unified primitive
                "base": base,         # start point
                "dir": axis_vec,      # UNIT direction
                "h": h,
                "r1": r1,
                "r2": r2,
                "center": center,
            })

        # ---- 2-D primitives (hull() of 2-D children is a 2-D op) ----
        elif node.node_type == "circle":
            p = node.params
            if "r" in p:
                rr = float(p["r"])
            elif "d" in p:
                rr = float(p["d"]) / 2.0
            else:
                try:
                    rr = float(node.csg_params.strip())
                except Exception:
                    rr = 1.0
            c = mat.multVec(Vector(0, 0, 0)) if mat else Vector(0, 0, 0)
            try:
                fn = int(round(float(p.get("$fn", 0) or 0)))
            except Exception:
                fn = 0
            out.append({"type": "circle", "center": c, "r": rr, "fn": fn})

        elif node.node_type == "square":
            p = node.params
            size = p.get("size", 1.0)
            if isinstance(size, (int, float)):
                w = h2 = float(size)
            elif isinstance(size, (list, tuple)) and len(size) >= 2:
                w, h2 = float(size[0]), float(size[1])
            else:
                w = h2 = 1.0
            ctr = p.get("center", False)
            if isinstance(ctr, str):
                ctr = ctr.lower() == "true"
            if ctr:
                local = [Vector(-w/2, -h2/2, 0), Vector(w/2, -h2/2, 0),
                         Vector(w/2, h2/2, 0), Vector(-w/2, h2/2, 0)]
            else:
                local = [Vector(0, 0, 0), Vector(w, 0, 0),
                         Vector(w, h2, 0), Vector(0, h2, 0)]
            pts = [(mat.multVec(v) if mat else v) for v in local]
            out.append({"type": "square", "pts": pts})

        elif node.node_type == "polygon":
            p = node.params
            pts = []
            for q in (p.get("points", []) or []):
                try:
                    v = Vector(float(q[0]), float(q[1]), 0)
                except Exception:
                    continue
                pts.append(mat.multVec(v) if mat else v)
            if pts:
                out.append({"type": "polygon", "pts": pts})
    return out


def try_hull_dispatch(normalized_hull):
    types = {p["type"] for p in normalized_hull}
    _dbg(f"Dispatch types={types} n={len(normalized_hull)}")

    # 2-D hull: all children are 2-D primitives → planar Face (NOT a 3-D hull).
    _TWO_D = {"circle", "square", "polygon"}
    if types and types <= _TWO_D:
        from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_2d import hull_2d
        return hull_2d(normalized_hull)

    if len(types) == 1:
        if types == {'sphere'}:
            return hull_spheres(normalized_hull)
        elif types == {'cylinder'}:
            return hull_cylinders_cones(normalized_hull)
        elif types == {'cube'}:
            return hull_cubes(normalized_hull)
        else:
            _warn(f"hull of all-{types} not handled natively")
            return None
    elif types == {'cube', 'cylinder'}:
        from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_mixed import hull_cylinders_and_cube
        return hull_cylinders_and_cube(normalized_hull)
    else:
        _warn(f"mixed-type hull not handled natively: {types}")
        return None
