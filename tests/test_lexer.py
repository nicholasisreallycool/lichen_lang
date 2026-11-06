import re

import pytest

from lichen.lexer import LexError, lex


def types(source):
    return [t.type for t in lex(source)]


def test_simple_assignment():
    assert types("x = 5") == ["NAME", "=", "NUMBER", "NEWLINE", "EOF"]


def test_ints_and_floats():
    tokens = lex("5 2.5")
    assert tokens[0].value == 5 and isinstance(tokens[0].value, int)
    assert tokens[1].value == 2.5 and isinstance(tokens[1].value, float)


def test_string_values():
    assert lex('"lichen"')[0].value == "lichen"
    assert lex('""')[0].value == ""


def test_keywords_vs_names():
    assert types("if iffy") == ["if", "NAME", "NEWLINE", "EOF"]


@pytest.mark.parametrize("word", [
    "const", "fn", "if", "elif", "else", "for", "in", "while",
    "return", "and", "or", "not", "true", "false", "break", "continue",
])
def test_every_keyword_is_recognised(word):
    assert lex(word)[0].type == word


@pytest.mark.parametrize("op", ["==", "!=", "<=", ">=", "++", "--", "+=", "-="])
def test_two_character_operators(op):
    assert lex(op)[0].type == op


@pytest.mark.parametrize("op", list("+-*/%=<>(){}[],"))
def test_one_character_tokens(op):
    assert lex(op)[0].type == op


def test_comment_is_ignored():
    assert types("x // a comment\ny") == ["NAME", "NEWLINE", "NAME", "NEWLINE", "EOF"]


def test_comment_only_line_produces_nothing():
    assert types("// hi\nx") == ["NAME", "NEWLINE", "EOF"]


def test_blank_lines_collapse_into_one_newline():
    assert types("a\n\n\nb") == ["NAME", "NEWLINE", "NAME", "NEWLINE", "EOF"]


def test_division_is_not_a_comment():
    assert types("6 / 2") == ["NUMBER", "/", "NUMBER", "NEWLINE", "EOF"]


def test_line_and_column_positions():
    tokens = lex("x = 5\ny")
    assert (tokens[1].line, tokens[1].col) == (1, 3)
    y = [t for t in tokens if t.value == "y"][0]
    assert (y.line, y.col) == (2, 1)


def test_empty_source():
    assert types("") == ["EOF"]


@pytest.mark.parametrize("source, message", [
    ('x = "abc', "Unterminated string"),
    ('x = "abc\ny"', "Unterminated string"),
    ("x = @", "Unexpected character"),
])
def test_lex_errors(source, message):
    with pytest.raises(LexError, match=re.escape(message)):
        lex(source)


def test_lex_error_has_position():
    with pytest.raises(LexError, match="line 1, col 5"):
        lex("x = @")
