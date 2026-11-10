import re

import pytest

from lichen.lexer import LexError, lex


def out(run, source):
    return run(source).rstrip("\n")


# =============== lexer ===============

@pytest.mark.parametrize("escape, expected", [
    (r"\n", "\n"),
    (r"\t", "\t"),
    (r"\r", "\r"),
    (r"\\", "\\"),
    (r'\"', '"'),
])
def test_each_escape_in_a_string(escape, expected):
    assert lex('"a' + escape + 'b"')[0].value == "a" + expected + "b"


def test_escaped_quote_does_not_end_the_string():
    assert lex(r'"say \"hi\""')[0].value == 'say "hi"'


def test_escaped_backslash_right_before_the_closing_quote():
    tokens = lex(r'"a\\" + "b"')
    assert tokens[0].value == "a\\"
    assert tokens[1].type == "+"


def test_strings_without_escapes_are_unchanged():
    assert lex('"plain text"')[0].value == "plain text"


@pytest.mark.parametrize("source, message", [
    (r'"a\qb"', "Unknown escape '\\q'"),
    (r'"a\0b"', "Unknown escape '\\0'"),
    (r'"a\xb"', "Unknown escape '\\x'"),
    (r'"a\{b"', "Unknown escape '\\{'"),
    ('"abc\\', "Unterminated string"),
    ('"abc\\\ndef"', "Unterminated string"),
    ('"abc\ndef"', "Unterminated string"),
])
def test_string_lex_errors(source, message):
    with pytest.raises(LexError, match=re.escape(message)):
        lex(source)


def test_unknown_escape_reports_its_position():
    with pytest.raises(LexError, match="line 1, col 7"):
        lex(r'x = "a\qb"')


# ---- inside f-strings ----

def test_escapes_in_the_text_part_of_an_fstring():
    assert lex(r'f"a\n{x}\t!"')[0].value == ["a\n", ("x", 1, 7), "\t!"]


def test_escaped_quote_in_fstring_text():
    assert lex(r'f"say \"hi\""')[0].value == ['say "hi"']


def test_fstring_unknown_escape_and_brace_hint():
    with pytest.raises(LexError, match=re.escape("Unknown escape '\\q'")):
        lex(r'f"a\qb"')
    with pytest.raises(LexError, match=re.escape("write '{{' for a literal brace")):
        lex(r'f"a\{b"')


def test_fstring_ending_in_a_backslash_is_unterminated():
    with pytest.raises(LexError, match="Unterminated f-string"):
        lex('f"abc\\')


def test_escaped_quote_inside_a_string_inside_an_fstring_expression():
    token = lex(r'f"{"a\"b"}"')[0]
    assert token.value == [(r'"a\"b"', 1, 4)]


# =============== running ===============

@pytest.mark.parametrize("source, expected", [
    (r'print("a\tb")', "a\tb"),
    (r'print("line1\nline2")', "line1\nline2"),
    (r'print(len("a\nb"))', "3"),
    (r'print("a\\b")', "a\\b"),
    (r'print("say \"hi\"")', 'say "hi"'),
    (r'print("a\\nb")', "a\\nb"),
    (r'print("one\ntwo\nthree".split("\n"))', r'["one", "two", "three"]'),
    (r'print("-".join(["a", "b"]) + "\n" + "c")', "a-b\nc"),
    (r'print("\t" in "a\tb")', "true"),
    (r'print("A\nB".lower())', "a\nb"),
    (r'print(f"a\tb {1 + 1}\n{"x\ty"}")', "a\tb 2\nx\ty"),
    (r'print(f"{"a\"b"} done")', 'a"b done'),
    (r'x = "tab\there"' + "\n" + r'print(x, len(x))', "tab\there 8"),
])
def test_escapes_when_running(run, source, expected):
    assert out(run, source) == expected


def test_strings_inside_lists_are_printed_re_escaped(run):
    assert out(run, r'print(["x\ny", "q\"uote", "back\\slash", "t\tab"])') == (
        r'["x\ny", "q\"uote", "back\\slash", "t\tab"]'
    )


def test_dictionaries_are_printed_re_escaped_too(run):
    assert out(run, r'print({"k\n": "v\"w"})') == r'{"k\n": "v\"w"}'


def test_echo_re_escapes_strings(run):
    assert run(r'"a\nb"', echo=True) == r'"a\nb"' + "\n"


def test_str_of_a_string_is_not_escaped(run):
    assert out(run, r'print(len(str("a\nb")))') == "3"


def test_printed_list_can_be_pasted_back_into_lichen(run):
    src = r'x = ["a\nb", "c\"d"]' + "\n" + r'print(x == ["a\nb", "c\"d"])'
    assert out(run, src) == "true"
