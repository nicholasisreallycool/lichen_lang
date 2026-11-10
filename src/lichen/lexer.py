from dataclasses import dataclass

KEYWORDS = {
    "const", "fn", "if", "elif", "else", "for", "in", "while",
    "return", "and", "or", "not", "true", "false", "break", "continue",
    "outer", "try", "except", "throw",
}

# the backslash escapes allowed inside strings
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"'}

TWO_CHAR = {"==", "!=", "<=", ">=", "++", "--", "+=", "-="}
ONE_CHAR = set("+-*/%=<>(){}[],:.")


@dataclass
class Token:
    type: str
    value: object
    line: int
    col: int


class LexError(Exception):
    pass


def read_string(source, i, line, line_start):
    """i points at the opening quote. Returns (text, index_after_the_closing_quote)."""
    n = len(source)
    start_col = i - line_start + 1
    i += 1
    chars = []
    while i < n and source[i] != '"':
        c = source[i]
        if c == "\n":
            break
        if c == "\\":
            nxt = source[i + 1:i + 2]
            if nxt == "" or nxt == "\n":
                break  # a backslash at the very end: the string never closes
            if nxt not in ESCAPES:
                raise LexError(f"Unknown escape '\\{nxt}' at line {line}, col {i - line_start + 1}")
            chars.append(ESCAPES[nxt])
            i += 2
            continue
        chars.append(c)
        i += 1
    if i >= n or source[i] != '"':
        raise LexError(f"Unterminated string at line {line}, col {start_col}")
    return "".join(chars), i + 1


def lex_fstring(source, i, line, line_start):
    """Scan f"..." starting at the 'f'. Returns (parts, index_after_the_closing_quote).
    parts is a list of plain strings and (expression_source, line, col) tuples."""
    n = len(source)
    start_col = i - line_start + 1
    i += 2  # skip the f and the opening quote
    parts, text = [], []
    while True:
        if i >= n or source[i] == "\n":
            raise LexError(f"Unterminated f-string at line {line}, col {start_col}")
        ch = source[i]
        if ch == '"':
            i += 1
            break
        if ch == "{":
            if source[i + 1:i + 2] == "{":  # {{ is a literal {
                text.append("{")
                i += 2
                continue
            if text:
                parts.append("".join(text))
                text = []
            begin = i + 1
            j = begin
            depth = 0
            while True:
                if j >= n or source[j] == "\n":
                    raise LexError(
                        f"Missing '}}' in f-string (or a string inside it is unterminated) "
                        f"at line {line}, col {i - line_start + 1}")
                cj = source[j]
                if cj == '"':  # a string inside the expression: skip over it whole
                    j += 1
                    while j < n and source[j] not in '"\n':
                        if source[j] == "\\" and source[j + 1:j + 2] not in ("", "\n"):
                            j += 2
                        else:
                            j += 1
                    if j >= n or source[j] != '"':
                        raise LexError(
                            f"Missing '}}' in f-string (or a string inside it is unterminated) "
                            f"at line {line}, col {i - line_start + 1}")
                    j += 1
                    continue
                if cj == "{":
                    depth += 1
                elif cj == "}":
                    if depth == 0:
                        break
                    depth -= 1
                j += 1
            chunk = source[begin:j]
            if not chunk.strip():
                raise LexError(f"Empty expression in f-string at line {line}, col {i - line_start + 1}")
            parts.append((chunk, line, begin - line_start + 1))
            i = j + 1
            continue
        if ch == "}":
            if source[i + 1:i + 2] == "}":  # }} is a literal }
                text.append("}")
                i += 2
                continue
            raise LexError(
                f"Single '}}' in f-string at line {line}, col {i - line_start + 1} "
                f"(write '}}}}' for a literal brace)")
        if ch == "\\":
            nxt = source[i + 1:i + 2]
            if nxt == "" or nxt == "\n":
                raise LexError(f"Unterminated f-string at line {line}, col {start_col}")
            if nxt not in ESCAPES:
                hint = " (write '{{' for a literal brace)" if nxt in "{}" else ""
                raise LexError(
                    f"Unknown escape '\\{nxt}' at line {line}, col {i - line_start + 1}{hint}")
            text.append(ESCAPES[nxt])
            i += 2
            continue
        text.append(ch)
        i += 1
    if text:
        parts.append("".join(text))
    return parts, i


def lex(source, line=1, col=1):
    """Turn source text into tokens. line and col say where the text starts in the
    original file (the parser uses this for expressions inside f-strings)."""
    tokens = []
    i = 0
    line_start = 1 - col
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
            text, i = read_string(source, i, line, line_start)
            add("STRING", text, start)

        elif c == "f" and source[i + 1:i + 2] == '"':
            start = i
            parts, i = lex_fstring(source, i, line, line_start)
            add("FSTRING", parts, start)

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
