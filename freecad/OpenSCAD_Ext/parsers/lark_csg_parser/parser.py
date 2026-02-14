from lark import Lark
from freecad.OpenSCAD_Ext.parsers.lark_csg_parser.grammar import CSG_GRAMMAR
from freecad.OpenSCAD.Ext.parsers.lark_csg_parser.transformer import CSGTransformer

def lark_parse_csg_file_to_AST(filename):

    with open(filename, "r", encoding="utf-8") as f:
        source = f.read()

    parser = Lark(
        CSG_GRAMMAR,
        parser="lalr",
        propagate_positions=True,
    )

    parse_tree = parser.parse(source)

    transformer = CSGTransformer()
    raw_ast_nodes = transformer.transform(parse_tree)

    return raw_ast_nodes


    return raw_ast_nodes
