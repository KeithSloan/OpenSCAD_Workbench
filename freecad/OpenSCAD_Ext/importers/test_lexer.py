import sys
import ply.lex as lex
import importAltCSG    # <-- your lexer module

print("USING LEXER FROM:", importAltCSG.__file__)

# Build lexer
lexer = lex.lex(module=importAltCSG, debug=True)

# Read file
with open(sys.argv[1], "r") as f:
    data = f.read()

lexer.input(data)

print("\n--- TOKENS ---")
while True:
    tok = lexer.token()
    if not tok:
        break
    print(tok)

