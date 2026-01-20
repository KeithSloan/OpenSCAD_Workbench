def normalize_ast(node):
    if node is None:
        return None

    node.children = [
        normalize_ast(c) for c in node.children if normalize_ast(c)
    ]

    # ONLY group is transparent
    if node.node_type == "group":
        if not node.children:
            return None
        if len(node.children) == 1:
            return node.children[0]

    return node

