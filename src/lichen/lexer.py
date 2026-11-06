from dataclasses import dataclass

KEYWORDS = {
    "const", "fn", "if", "elif", "else", "for", "in", "while",
    "return", "and", "or", "not", "true", "false",
}

TWO_CHAR = {"==", "!=", "<=", ">=", "++", "--", "+=", "-="}
ONE_CHAR = set("+-*/%=<>(){}[],")


@dataclass
class Token:
    type: str      # "NUMBER", "STRING", "NAME", "NEWLINE", "EOF", or the keyword/operator text
    value: object
    line: int
    col: int


class LexError(Exception):
    pass


def lex(source):
    tokens = []
    i = 0
    line = 1
    line_start = 0
    n = len(source)

    def add(type_, value, start):
        tokens.append(Token(type_, value, line, start - line_start + 1))

    while i < n:
        c = source[i]

        if c in " \t\r":
            i += 1

        elif c == "\n":
            if tokens and tokens[-1].type != "NEWLINE":
                add("NEWLINE", "\n", i)
            i += 1
            line += 1
            line_start = i

        elif source.startswith("//", i):
            while i < n and source[i] != "\n":
                i += 1

        elif c.isdigit():
            start = i
            while i < n and source[i].isdigit():
                i += 1
            if i < n and source[i] == "." and i + 1 < n and source[i + 1].isdigit():
                i += 1
                while i < n and source[i].isdigit():
                    i += 1
                add("NUMBER", float(source[start:i]), start)
            else:
                add("NUMBER", int(source[start:i]), start)

        elif c == '"':
            start = i
            i += 1
            while i < n and source[i] not in '"\n':
                i += 1
            if i >= n or source[i] != '"':
                raise LexError(f"Unterminated string at line {line}, col {start - line_start + 1}")
            add("STRING", source[start + 1:i], start)
            i += 1

        elif c.isalpha() or c == "_":
            start = i
            while i < n and (source[i].isalnum() or source[i] == "_"):
                i += 1
            word = source[start:i]
            if word in KEYWORDS:
                add(word, word, start)
            else:
                add("NAME", word, start)

        elif source[i:i + 2] in TWO_CHAR:
            add(source[i:i + 2], source[i:i + 2], i)
            i += 2

        elif c in ONE_CHAR:
            add(c, c, i)
            i += 1

        else:
            raise LexError(f"Unexpected character {c!r} at line {line}, col {i - line_start + 1}")

    if tokens and tokens[-1].type != "NEWLINE":
        add("NEWLINE", "\n", i)
    add("EOF", None, i)
    return tokens
