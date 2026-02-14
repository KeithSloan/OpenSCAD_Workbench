from lark import Transformer
import ast_nodes


class CSGTransformer(Transformer):

    def start(self, items):
        return items

    # -------------------------
    # Primitives
    # -------------------------

    def primitive(self, items):
        keyword = items[0]
        params, children = self._extract(items[1:] if len(items) > 1 else [])

        return self._build_node(keyword, params, children)

    # -------------------------
    # Boolean ops
    # -------------------------

    def boolean_op(self, items):
        keyword = items[0]
        params, children = self._extract(items[1:])
        return self._build_node(keyword, params, children)

    # -------------------------
    # Transforms
    # -------------------------

    def transform(self, items):
        keyword = items[0]
        params, children = self._extract(items[1:])
        return self._build_node(keyword, params, children)

    # -------------------------
    # Helpers
    # -------------------------

    def call_block(self, items):
        return items

    def block(self, items):
        return items

    def param_list(self, items):
        return items

    def param(self, items):
        if len(items) == 2:
            return (items[0], items[1])
        return items[0]

    def vector(self, items):
        return items

    def NAME(self, token):
        return str(token)

    def NUMBER(self, token):
        return float(token)

    # -------------------------
    # Internal utilities
    # -------------------------

    def _extract(self, items):
        params = {}
        children = []

        for item in items:
            if isinstance(item, tuple):
                params[item[0]] = item[1]
            elif isinstance(item, list):
                children.extend(item)

        return params, children

    def _build_node(self, keyword, params, children):

        mapping = {
            "cube": ast_nodes.Cube,
            "sphere": ast_nodes.Sphere,
            "cylinder": ast_nodes.Cylinder,
            "union": ast_nodes.Union,
            "difference": ast_nodes.Difference,
            "intersection": ast_nodes.Intersection,
            "hull": ast_nodes.Hull,
            "group": ast_nodes.Group,
            "translate": ast_nodes.Translate,
            "rotate": ast_nodes.Rotate,
            "scale": ast_nodes.Scale,
            "multmatrix": ast_nodes.MultMatrix,
        }

        cls = mapping.get(keyword, None)

        if cls is None:
            return ast_nodes.UnknownNode(keyword, params=params, children=children)

        if keyword in ["union", "difference", "intersection", "hull", "group"]:
            return cls(children=children, params=params)

        return cls(params=params, children=children)
