import sys

from lichen.lexer import lex, LexError
from lichen.parser import parse, ParseError
from lichen.nodes import dump


def main():
    args = sys.argv[1:]

    if not args:
        print("lichen 0.1.0 (REPL coming soon)")
        return

    flag = None
    if args[0] in ("--tokens", "--ast"):
        flag = args[0]
        args = args[1:]

    if not args:
        print("Error: no file given")
        sys.exit(1)

    try:
        with open(args[0], encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: can't find file {args[0]}")
        sys.exit(1)

    try:
        tokens = lex(source)
        if flag == "--tokens":
            for t in tokens:
                print(f"{t.line}:{t.col}  {t.type}  {t.value!r}")
            return
        tree = parse(tokens)
    except (LexError, ParseError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    if flag == "--ast":
        print(dump(tree))
    else:
        print("Parsed OK (nothing to run yet)")
