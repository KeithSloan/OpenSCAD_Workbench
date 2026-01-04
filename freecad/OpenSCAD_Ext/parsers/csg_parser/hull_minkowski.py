import Part

def try_hull(stack):
    """
    Try to handle a hull operation on the top objects in the stack.
    Return Part.Shape if successful, else None
    """
    if len(stack) < 2:
        return None
    # Example: convex hull of last two objects
    shape1 = stack.pop()
    shape2 = stack.pop()
    try:
        # For simplicity, create hull of vertices
        pts = shape1.Vertexes + shape2.Vertexes
        pts_vectors = [v.Point for v in pts]
        hull = Part.makePolygon(pts_vectors)
        hull_solid = hull.makeSolid()
        return hull_solid
    except Exception:
        # Cannot handle — return None
        return None

def try_minkowski(stack):
    """
    Try to handle a minkowski operation.
    Return Part.Shape if successful, else None
    """
    if len(stack) < 2:
        return None
    shape1 = stack.pop()
    shape2 = stack.pop()
    try:
        # Placeholder: real Minkowski would be more complex
        # For now return None to fallback
        return None
    except Exception:
        return None

