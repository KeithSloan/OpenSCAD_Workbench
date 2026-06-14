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

            elif nt in ("sphere", "cube", "cylinder"):
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
            result = try_hull_dispatch(geo)
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

    if len(all_shapes) >= 2:
        from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_mixed_curve import (
            hull_sphere_polyhedron
        )
        from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_brep import (
            hull_brep_shapes
        )
        import Part as _Part

        spheres, polys = [], []
        for s in all_shapes:
            try:
                if any(isinstance(f.Surface, _Part.Sphere) for f in s.Faces):
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

        # ── General silhouette + loft (smooth BRep, no faceting) ─────
        if len(all_shapes) == 2:
            from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_brep_loft import (
                hull_brep_loft
            )
            _dbg("  trying brep loft (2 shapes)")
            try:
                result = hull_brep_loft(all_shapes)
                if result is not None:
                    _dbg("  brep loft OK")
                    return result
                _dbg("  brep loft returned None")
            except Exception as ex:
                _dbg(f"  brep loft err: {ex}")

        # ── General BRep faceted (last resort) ────────────────────────
        _dbg("  loft unavailable → faceted BRep fallback")
        try:
            result = hull_brep_shapes(all_shapes)
            _dbg("  general BRep (faceted) OK")
            return result
        except Exception as ex:
            _dbg(f"  general BRep err: {ex}")

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
    return out


def try_hull_dispatch(normalized_hull):
    types = {p["type"] for p in normalized_hull}
    write_log("Hull", f"Dispatch types={types}")

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
