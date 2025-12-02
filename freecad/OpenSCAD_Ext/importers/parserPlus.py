def process_csg_ast(ast_root, is_brep_convertible, process_brep_node, process_openscad_subtree):
    """
    ast_root: Program node
    is_brep_convertible: function(node) -> bool
    process_brep_node: function(node) for FreeCAD BREP conversion
    process_openscad_subtree: function(node) to send entire subtree to OpenSCAD
    """

    for node in ast_root.statements:
        process_node_recursive(node, None,
                               is_brep_convertible,
                               process_brep_node,
                               process_openscad_subtree)


def process_node_recursive(node, parent_is_compound,
                           is_brep_convertible,
                           process_brep_node,
                           process_openscad_subtree):

    is_compound = isinstance(node, OpNode) and node.name in ('hull', 'minkowski')

    if is_compound:
        # -----------------------------
        # CASE A: hull/minkowski
        # -----------------------------
        if is_brep_convertible(node):
            # ✔ BREP allowed
            for child in node.children:
                process_node_recursive(child, True,
                                       is_brep_convertible,
                                       process_brep_node,
                                       process_openscad_subtree)
        else:
            # ✘ Too complex – fallback to OpenSCAD
            process_openscad_subtree(node)
        return

    # -----------------------------
    # CASE B: normal operation
    # -----------------------------
    if isinstance(node, OpNode):
        # BREP‐convert normal operations
        process_brep_node(node)

        # Now descend into children
        for child in node.children:
            process_node_recursive(child, False,
                                   is_brep_convertible,
                                   process_brep_node,
                                   process_openscad_subtree)

    else:
        # Raw primitive or simple stmt
        process_brep_node(node)

