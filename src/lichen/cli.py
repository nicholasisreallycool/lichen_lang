import sys
from lichen.lexer import lex, LexError


def main():
    args = sys.argv[1:]

    if not args:
        print("lichen 0.1.0 (REPL coming soon)")
        return

    show_tokens = False
    if args[0] == "--tokens":
        show_tokens = True
        args = args[1:]

    with open(args[0], encoding="utf-8") as f:
        source = f.read()

    try:
        tokens = lex(source)
    except LexError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if show_tokens:
        for t in tokens:
            print(f"{t.line}:{t.col}  {t.type}  {t.value!r}")
    else:
        print("Lexed OK (nothing to run yet)")
