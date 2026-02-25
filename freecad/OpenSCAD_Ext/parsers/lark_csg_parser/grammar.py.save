from lark import Lark, Transformer, v_args

CSG_GRAMMAR = r"""
?start: node+

?node: node_header "{" node* "}"     -> block_node
     | node_header                     -> leaf_node

node_header: NAME "(" [params] ")"     -> node_header

?params: param ("," param)*
?param: number
      | vector
      | string
      | NAME                         -> name_param
      | "true"                        -> true
      | "false"                       -> false

vector: "[" [number ("," number)*] "]"

number: SIGNED_NUMBER

string: ESCAPED_STRING

NAME: /[a-zA-Z_][a-zA-Z0-9_]*/

%import common.SIGNED_NUMBER
%import common.ESCAPED_STRING
%import common.WS
%ignore WS
%ignore /\/\/[^\n]*/   // C++ style comments
"""


