import sys

from lichen.lexer import lex, LexError
from lichen.parser import parse, ParseError
from lichen.evaluator import Interpreter, LichenRuntimeError
from lichen.nodes import dump

VERSION = "0.5.0"
OPENERS = ("(", "{", "[")
CLOSERS = (")", "}", "]")


def repl():
    interp = Interpreter()
    print(f"lichen {VERSION}  (type exit to quit)")
    buffer = ""
    while True:
        try:
            line = input("... " if buffer else "lichen> ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            buffer = ""
            continue

        if not buffer and line.strip() in ("exit", "quit"):
            break

        buffer += line + "\n"
        try:
            tokens = lex(buffer)
            depth = sum(t.type in OPENERS for t in tokens) - sum(t.type in CLOSERS for t in tokens)
            if depth > 0:
                continue  # unfinished block, keep reading lines
            if len(tokens) > 1:
                interp.run(parse(tokens), echo=True)
        except (LexError, ParseError) as e:
            print(f"Error: {e}")
        except LichenRuntimeError as e:
            print(f"Runtime error: {e}")
        except KeyboardInterrupt:
            print("\nInterrupted")
        buffer = ""


def main():
    args = sys.argv[1:]

    if not args:
        repl()
        return

    if args[0] in ("--version", "-v"):
        print(f"lichen {VERSION}")
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
        if flag == "--ast":
            print(dump(tree))
            return
    except (LexError, ParseError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        Interpreter().run(tree)
    except LichenRuntimeError as e:
        print(f"Runtime error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)
