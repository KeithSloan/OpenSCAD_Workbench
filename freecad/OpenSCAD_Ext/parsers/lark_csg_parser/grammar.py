CSG_GRAMMAR = r"""
    start: statement*

    ?statement: primitive
              | boolean_op
              | transform
              | ";"

    // -------------------------
    // Primitives
    // -------------------------

    primitive: "cube" call_block?
             | "sphere" call_block?
             | "cylinder" call_block?

    // -------------------------
    // Boolean ops
    // -------------------------

    boolean_op: "union" call_block
              | "difference" call_block
              | "intersection" call_block
              | "hull" call_block
              | "group" call_block

    // -------------------------
    // Transforms
    // -------------------------

    transform: "translate" call_block
             | "rotate" call_block
             | "scale" call_block
             | "multmatrix" call_block

    // -------------------------
    // Call with optional params and block
    // -------------------------

    call_block: "(" param_list? ")" block?
              | block

    block: "{" statement* "}"

    param_list: param ("," param)*
    param: NAME "=" expr
         | expr

    ?expr: NUMBER
         | vector
         | NAME

    vector: "[" [expr ("," expr)*] "]"

    NAME: /[a-zA-Z_]\w*/
    NUMBER: /-?[0-9]+(\.[0-9]+)?/

    %import common.WS
    %ignore WS
    %ignore /\/\/[^\n]*/
"""
