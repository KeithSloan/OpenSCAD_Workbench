def parse_csg(csg_text, node_classes):
    parser = Lark(CSG_GRAMMAR, start='start', parser='lalr')
    tree = parser.parse(csg_text)
    ast = CSGTransformer(node_classes).transform(tree)
    return ast

