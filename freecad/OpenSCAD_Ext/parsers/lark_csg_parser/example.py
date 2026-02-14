# Example NODE_CLASSES
class Node:
    def __init__(self, *params):
        self.params = params
        self.children = []

    def __repr__(self):
        return f"{self.__class__.__name__}(params={self.params}, children={self.children})"

NODE_CLASSES = {
    "sphere": Node,
    "cube": Node,
    "union": Node,
    "translate": Node,
}

csg_code = """
union() {
    sphere(r=10);
    translate([5,0,0]) {
        cube([2,2,2]);
    }
}
"""

ast = parse_csg(csg_code, NODE_CLASSES)
for node in ast:
    print(node)

