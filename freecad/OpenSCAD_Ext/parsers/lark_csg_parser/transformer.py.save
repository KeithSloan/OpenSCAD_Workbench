@v_args(inline=True)
class CSGTransformer(Transformer):
    def __init__(self, node_classes):
        self.node_classes = node_classes

    def block_node(self, header, *children):
        cls, params = header
        obj = cls(*params)
        obj.children = list(children)
        return obj

    def leaf_node(self, header):
        cls, params = header
        return cls(*params)

    def node_header(self, name, *params):
        cls = self.node_classes.get(str(name))
        if cls is None:
            raise ValueError(f"Unknown node type: {name}")
        return cls, list(params)

    def number(self, n):
        return float(n)

    def string(self, s):
        return s[1:-1]  # remove quotes

    def vector(self, *vals):
        return list(vals)

    def true(self):
        return True

    def false(self):
        return False

    def name_param(self, name):
        return str(name)

