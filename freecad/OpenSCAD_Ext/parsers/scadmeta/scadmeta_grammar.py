"""
Lark EBNF grammar for OpenSCAD source-file metadata extraction.

The grammar covers enough of the OpenSCAD language to reliably identify:
  - include / use statements
  - Top-level variable assignments
  - Module definitions (name + parameter list)
  - Function definitions (name + parameter list)
  - Top-level geometry / executable calls (marks a file as PURE_SCAD)

Expression bodies inside module and function definitions are absorbed by the
``block`` / ``expr`` rules so the parser does not crash on complex geometry
code.  We use parser="earley" with lexer="dynamic" so that the ``<path>``
syntax in include/use statements does not conflict with the ``<`` comparison
operator in expressions.
"""

SCAD_META_GRAMMAR = r"""
    start: statement*

    // ---------------------------------------------------------------
    // Top-level statements
    // ---------------------------------------------------------------

    ?statement: include_stmt
              | use_stmt
              | assign_stmt
              | module_def
              | function_def
              | if_stmt
              | for_stmt
              | let_stmt
              | modifier_stmt
              | call_stmt
              | ";"

    include_stmt : "include" ANGLE_PATH
    use_stmt     : "use"     ANGLE_PATH

    // variable assignment: name = expr ;
    assign_stmt  : NAME "=" expr ";"

    // module module_name(params) { body }
    module_def   : "module" NAME "(" param_list? ")" block

    // function function_name(params) = expr ;
    function_def : "function" NAME "(" param_list? ")" "=" expr ";"

    // control flow (may appear at top level in pure-scad files)
    if_stmt      : "if" "(" expr ")" stmt_body ("else" (if_stmt | stmt_body))?
    for_stmt     : "for" "(" for_assignments ")" stmt_body
    let_stmt     : "let" "(" assign_list ")" stmt_body

    // geometry modifier: %, #, !, *
    modifier_stmt : MODIFIER statement

    // geometry call followed by ; or a child statement/block
    call_stmt    : call_expr (";" | stmt_body)

    // ---------------------------------------------------------------
    // Shared sub-rules
    // ---------------------------------------------------------------

    stmt_body    : block | call_stmt | if_stmt | for_stmt | let_stmt | modifier_stmt

    block        : "{" statement* "}"

    call_expr    : NAME "(" arg_list? ")"

    param_list   : param ("," param)*
    param        : NAME ("=" expr)?

    arg_list     : arg ("," arg)*
    arg          : (NAME "=")? expr

    for_assignments : for_assign ("," for_assign)*
    for_assign      : NAME "=" expr
                    | "[" NAME ("," NAME)* "]" "=" expr

    assign_list  : NAME "=" expr ("," NAME "=" expr)*

    // ---------------------------------------------------------------
    // Expression grammar  (operator precedence via rule nesting)
    // ---------------------------------------------------------------

    ?expr        : ternary

    ?ternary     : or_expr
                 | or_expr "?" ternary ":" ternary

    ?or_expr     : and_expr
                 | or_expr "||" and_expr

    ?and_expr    : not_expr
                 | and_expr "&&" not_expr

    ?not_expr    : cmp_expr
                 | "!" not_expr

    ?cmp_expr    : add_expr
                 | cmp_expr "==" add_expr  -> eq
                 | cmp_expr "!=" add_expr  -> neq
                 | cmp_expr "<"  add_expr  -> lt
                 | cmp_expr "<=" add_expr  -> lte
                 | cmp_expr ">"  add_expr  -> gt
                 | cmp_expr ">=" add_expr  -> gte

    ?add_expr    : mul_expr
                 | add_expr "+" mul_expr   -> add
                 | add_expr "-" mul_expr   -> sub

    ?mul_expr    : unary_expr
                 | mul_expr "*" unary_expr -> mul
                 | mul_expr "/" unary_expr -> div
                 | mul_expr "%" unary_expr -> mod

    ?unary_expr  : postfix_expr
                 | "-" unary_expr          -> neg
                 | "+" unary_expr          -> pos

    ?postfix_expr : primary_expr
                  | postfix_expr "[" expr "]"    -> index
                  | NAME "(" arg_list? ")"        -> func_call

    ?primary_expr : NUMBER                 -> number
                  | ESCAPED_STRING         -> string
                  | BOOL                   -> bool_val
                  | "undef"               -> undef_val
                  | NAME                  -> name_ref
                  | "(" expr ")"
                  | vector
                  | range_expr
                  | let_expr

    vector       : "[" (expr ("," expr)*)? "]"
    range_expr   : "[" expr ":" expr (":" expr)? "]"
    let_expr     : "let" "(" assign_list ")" expr

    // ---------------------------------------------------------------
    // Terminals
    // ---------------------------------------------------------------

    // Path between angle brackets – only valid after include/use keywords.
    // Defined as a single terminal so the dynamic lexer can match it
    // without conflicting with < / > used as comparison operators.
    ANGLE_PATH  : /\<[^>]+\>/

    MODIFIER    : /[%#!*]/

    BOOL        : "true" | "false"

    // OpenSCAD identifiers may start with $ (special variables)
    NAME        : /[\$]?[a-zA-Z_][a-zA-Z0-9_]*/

    // Numbers: optional leading minus, optional decimal, optional exponent
    NUMBER      : /-?[0-9]+(\.[0-9]+)?(e[+-]?[0-9]+)?/i

    %import common.ESCAPED_STRING
    %import common.WS
    %ignore WS
    %ignore /\/\/[^\n]*/
    %ignore /\/\*(.|\n)*?\*\//
"""
