import FreeCAD
from FreeCAD import Vector, Matrix
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log


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
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_spheres import hull_spheres
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_cylinders import hull_cylinders_cones
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_cubes import hull_cubes


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
        """Extract a Part.Shape from process_AST_node return value."""
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
        """Walk children: collect simple primitives, descend into complex ones."""
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

            elif nt == "hull":
                write_log("Hull",
                    f"Nested hull — flattening {len(child.children or [])} children")
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
                    write_log("Hull", "intersection: no usable primitive, creating shape")
                    try:
                        _extract_shape(process_AST_node(child))
                    except Exception as ex:
                        write_log("Hull", f"  intersection shape failed: {ex}")

            else:
                # Complex op: boolean, minkowski, extrude, offset, etc.
                write_log("Hull",
                    f"Descending into '{nt}' — creating child shape")
                try:
                    _extract_shape(process_AST_node(child))
                except Exception as ex:
                    write_log("Hull", f"  {nt} shape failed: {ex}")

    _descend(node.children)

    write_log("Hull",
        f"Collected: {len(primitives)} primitives, {len(shapes)} complex shapes")

    # ── Path 1: AST-based dispatch (only when ALL children are simple) ─
    if len(primitives) >= 2 and len(shapes) == 0:
        geo = normalize_primitives(primitives, matrices)
        if geo is not None:
            write_log("Hull", f"Dispatching AST hull with {len(geo)} primitive(s)")
            result = try_hull_dispatch(geo)
            if result is not None:
                return result

    # ── Convert primitives to shapes if needed ────────────────────────
    all_shapes = list(shapes)
    if not all_shapes or len(all_shapes) < 2:
        import FreeCAD as _FC
        for child, mat in zip(primitives, matrices):
            try:
                r = process_AST_node(child)
                # Apply the accumulated transform matrix to the shape
                items = r if isinstance(r, list) else [r]
                for item in items:
                    if isinstance(item, tuple) and len(item) >= 2:
                        s, pl = item[0], item[1]
                    else:
                        s, pl = item, None
                    if s is not None:
                        s = s.Shape if hasattr(s, 'Shape') else s
                        # Combine child's own placement with accumulated matrix
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

    write_log("Hull", f"  shape-based: {len(all_shapes)} total shapes")

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

        for sp in spheres:
            for po in polys:
                try:
                    result = hull_sphere_polyhedron(sp, po)
                    if result is not None:
                        write_log("Hull", "  sphere+poly analytical OK")
                        return result
                except Exception as ex:
                    write_log("Hull", f"  sphere+poly err: {ex}")

        try:
            result = hull_brep_shapes(all_shapes)
            write_log("Hull", "  general BRep OK")
            return result
        except Exception as ex:
            write_log("Hull", f"  general BRep err: {ex}")

    return None


_COMPLEX_OPS = {
    "difference", "union", "hull", "minkowski",
    "linear_extrude", "rotate_extrude", "offset", "projection",
}


def _subtree_has_complex_op(node):
    """
    Return True if the node's subtree contains any operation that could
    dramatically reshape a primitive — i.e. anything beyond transparent
    wrappers (group, color, multmatrix) and leaf primitives.

    Used by the intersection handler to decide whether the clipping
    geometry is 'simple enough' to safely ignore (e.g. a linear_extrude
    sector polygon) versus 'complex' (e.g. difference/hull chains that
    reduce the primitive to a tiny fraction of its original extent).

    Complex ops that trigger fallback:
      difference, union, hull, minkowski, linear_extrude, rotate_extrude,
      offset, projection — anything constructive or extrusive.
    """
    if node.node_type in _COMPLEX_OPS:
        return True
    for child in (node.children or []):
        if _subtree_has_complex_op(child):
            return True
    return False


def _first_complex_op(node):
    """Like _subtree_has_complex_op but returns the first complex op node_type
    found in the subtree, or None if the subtree is clean."""
    if node.node_type in _COMPLEX_OPS:
        return node.node_type
    for child in (node.children or []):
        found = _first_complex_op(child)
        if found:
            return found
    return None


def collect_primitives(children, primitives_out, matrices_out, parent_matrix=None, _fail=None):
    """Walk hull children accumulating (primitive_node, matrix) pairs.

    Returns True on success.  On failure, appends a human-readable reason
    string to *_fail* (if provided) before returning False — so callers can
    report exactly why the native hull path was abandoned.
    """
    def _fail_with(reason):
        if _fail is not None and not _fail:   # only record the first (root) reason
            _fail.append(reason)
        return False

    for child in children:
        matrix = (
            parent_matrix.multiply(child.matrix)
            if (parent_matrix and hasattr(child, "matrix"))
            else (child.matrix if hasattr(child, "matrix") else parent_matrix)
        )

        if child.node_type in ("group", "color"):
            # color is a transparent wrapper — recurse into children, ignoring colour
            if not collect_primitives(child.children, primitives_out, matrices_out, matrix, _fail):
                return False

        elif child.node_type == "multmatrix":
            if not hasattr(child, "matrix"):
                return _fail_with(f"multmatrix child has no matrix attribute")
            if not collect_primitives(child.children, primitives_out, matrices_out, matrix, _fail):
                return False

        elif child.node_type == "hull":
            # Nested hull: flatten by recursing into its children.
            # The convex hull of a set of convex shapes equals the convex hull
            # of all their constituent primitives, so we can collect them directly
            # without losing correctness.  Any transform already accumulated in
            # `matrix` is passed through unchanged (hull itself applies no transform).
            nested_summary = ", ".join(
                f"{c.node_type}({len(c.children or [])})" for c in (child.children or [])
            )
            write_log("Hull",
                f"Nested hull detected — flattening {len(child.children or [])} "
                f"children into parent: [{nested_summary}]")
            if not collect_primitives(child.children, primitives_out, matrices_out, matrix, _fail):
                return False

        elif child.node_type in ("sphere", "cube", "cylinder"):
            primitives_out.append(child)
            matrices_out.append(matrix if matrix else Matrix())

        elif child.node_type == "intersection":
            # An intersection clips a primitive to a sub-region.
            #
            # Safe approximation: hull(A ∩ B, ...) ⊆ hull(A, ...) because
            # clipping can only shrink the hull boundary, never expand it.
            # We use the first child primitive as a stand-in for the
            # intersection — BUT only when the clipping children are simple
            # (transparent wrappers + primitives).  When a clipping child
            # contains constructive ops (difference, hull, linear_extrude …)
            # the intersection result may be far smaller than the primitive
            # (e.g. a 30 mm cube clipped down to a tiny peg shape), making
            # the approximation produce grossly wrong hull geometry.
            # In that case, fail here so the caller falls back to OpenSCAD CLI.
            clipping_children = (child.children or [])[1:]  # everything after the first
            for clip in clipping_children:
                op = _first_complex_op(clip)
                if op:
                    reason = (
                        f"intersection clipping child ('{clip.node_type}') contains "
                        f"complex op '{op}' — hull(A∩B) approximation unsafe; "
                        f"the clipped shape may be far smaller than the raw primitive"
                    )
                    write_log("Hull", reason)
                    return _fail_with(reason)

            found = False
            for sub in child.children:
                sub_prims, sub_mats = [], []
                if collect_primitives([sub], sub_prims, sub_mats, matrix, _fail):
                    if sub_prims:
                        primitives_out.extend(sub_prims)
                        matrices_out.extend(sub_mats)
                        found = True
                        break
            if not found:
                reason = "intersection: no usable primitive child found"
                write_log("Hull", reason)
                return _fail_with(reason)

        else:
            reason = f"unsupported node inside hull: '{child.node_type}'"
            _warn(f"{reason} — cannot build native BRep hull")
            return _fail_with(reason)

    return True

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

            write_log("cylinder",f"params {node.params}")

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
    write_log("Normalized ",normalized_hull)

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
