import re

import pytest

from lichen.evaluator import LichenRuntimeError
from lichen.lexer import LexError, lex
from lichen.nodes import Binary, FString, MethodCall, Name, Num, Str
from lichen.parser import ParseError, parse


def body(source):
    return parse(lex(source)).body


def out(run, source):
    return run(source).rstrip("\n")


# =============== lexer: f-strings ===============

def test_fstring_is_one_token_with_parts():
    token = lex('f"hi {x}!"')[0]
    assert token.type == "FSTRING"
    assert token.value == ["hi ", ("x", 1, 7), "!"]


def test_doubled_braces_are_literal_braces():
    assert lex('f"{{x}}"')[0].value == ["{x}"]


def test_plain_and_empty_fstrings():
    assert lex('f"abc"')[0].value == ["abc"]
    assert lex('f""')[0].value == []


def test_strings_inside_an_expression_dont_end_the_fstring():
    assert lex('f"{d["a"]}"')[0].value == [('d["a"]', 1, 4)]


def test_braces_inside_an_expression_are_balanced():
    chunk = lex('f"{ {"a": 1}["a"] }"')[0].value[0][0]
    assert chunk == ' {"a": 1}["a"] '


def test_expression_position_on_a_later_line():
    tokens = lex('x = 1\nprint(f"{y}")')
    fstring = [t for t in tokens if t.type == "FSTRING"][0]
    assert fstring.value == [("y", 2, 10)]


def test_f_on_its_own_is_still_a_name():
    assert lex("f")[0].type == "NAME"
    assert lex("fx = 1")[0].value == "fx"
    assert [t.type for t in lex("f(1)")][:2] == ["NAME", "("]


@pytest.mark.parametrize("source, message", [
    ('f"abc', "Unterminated f-string"),
    ('f"abc\ndef"', "Unterminated f-string"),
    ('f"{x"', "Missing '}' in f-string"),
    ('f"{x', "Missing '}' in f-string"),
    ('f"{"abc}"', "Missing '}' in f-string"),
    ('f"{}"', "Empty expression in f-string"),
    ('f"{ }"', "Empty expression in f-string"),
    ('f"a}b"', "Single '}' in f-string"),
])
def test_fstring_lex_errors(source, message):
    with pytest.raises(LexError, match=re.escape(message)):
        lex(source)


def test_dot_is_a_token():
    assert [t.type for t in lex("a.b")][:3] == ["NAME", ".", "NAME"]


def test_decimal_numbers_still_lex_as_one_token():
    tokens = lex("2.5")
    assert tokens[0].type == "NUMBER" and tokens[0].value == 2.5


# =============== parser: f-strings ===============

def test_fstring_node_mixes_text_and_expressions():
    node = body('s = f"a{x + 1}b"')[0].value
    assert isinstance(node, FString)
    assert node.parts[0] == Str("a")
    assert isinstance(node.parts[1], Binary)
    assert node.parts[2] == Str("b")


def test_fstring_expression_can_hold_calls_and_methods():
    node = body('s = f"{f(1)} {name.upper()}"')[0].value
    assert type(node.parts[0]).__name__ == "Call"
    assert type(node.parts[2]).__name__ == "MethodCall"


def test_nested_fstring():
    node = body('s = f"{f"{x}"}"')[0].value
    assert isinstance(node.parts[0], FString)


@pytest.mark.parametrize("source, message, position", [
    ('x = f"{1 +}"', "Expected an expression", "line 1, col 11"),
    ('x = f"{x y}"', "Unexpected 'y' in f-string expression", "line 1, col 10"),
    ('x = f"{x:.2f}"', "Unexpected ':' in f-string expression", "line 1, col 9"),
])
def test_fstring_parse_errors_point_at_the_right_place(source, message, position):
    with pytest.raises(ParseError, match=re.escape(message) + ".*" + position):
        parse(lex(source))


def test_lex_error_inside_an_expression_has_file_position():
    with pytest.raises(LexError, match="Unexpected character '@' at line 1, col 8"):
        parse(lex('x = f"{@}"'))


# =============== parser: method calls ===============

def test_method_call_node():
    node = body("s.upper()")[0].expr
    assert isinstance(node, MethodCall)
    assert node.name == "upper" and node.args == []
    assert node.obj == Name("s", 1)


def test_method_call_with_arguments():
    node = body('s.replace("a", "b")')[0].expr
    assert node.args == [Str("a"), Str("b")]


def test_method_chains_left_to_right():
    node = body("s.strip().upper()")[0].expr
    assert node.name == "upper"
    assert node.obj.name == "strip"


def test_methods_work_on_literals_indexes_and_call_results():
    assert body('"a".upper()')[0].expr.obj == Str("a")
    assert type(body("xs[0].upper()")[0].expr.obj).__name__ == "Index"
    assert type(body("f(1).upper()")[0].expr.obj).__name__ == "Call"


@pytest.mark.parametrize("source, message", [
    ("s.upper", "Expected '(' after '.upper'"),
    ("s.", "Expected a method name after '.'"),
    ("s.upper() = 1", "Can't assign to this expression"),
])
def test_method_parse_errors(source, message):
    with pytest.raises(ParseError, match=re.escape(message)):
        parse(lex(source))


# =============== running f-strings ===============

@pytest.mark.parametrize("source, expected", [
    ('name = "lichen"\nprint(f"Hello, {name}!")', "Hello, lichen!"),
    ('print(f"{1 + 2}")', "3"),
    ('print(f"a{ 1 + 1 }b")', "a2b"),
    ('x = 1\ny = 2\nprint(f"{x}{y}")', "12"),
    ('print(f"{true} {false}")', "true false"),
    ('print(f"{3.5}")', "3.5"),
    ('print(f"{[1, "a"]}")', '[1, "a"]'),
    ('print(f"{{literal}} {1}")', "{literal} 1"),
    ('print(f"{"hi".upper()}")', "HI"),
    ('d = {"a": 1}\nprint(f"{d["a"]}")', "1"),
    ('print(f"{ {"a": 1}["a"] }")', "1"),
    ('print(f"{f"{1}"}")', "1"),
    ('print(f"")', ""),
    ('print(f"plain text")', "plain text"),
    ('print(f"a" + f"b")', "ab"),
    ('print([f"{1}", f"{2}"])', '["1", "2"]'),
    ('fn fib(n) {\n  if n < 2 {\n    return n\n  }\n  return fib(n - 1) + fib(n - 2)\n}\nprint(f"fib(10) = {fib(10)}")',
     "fib(10) = 55"),
    ('for i in range(1, 4) {\n  print(f"{i} squared is {i * i}")\n}',
     "1 squared is 1\n2 squared is 4\n3 squared is 9"),
])
def test_fstrings(run, source, expected):
    assert out(run, source) == expected


def test_fstring_error_reports_the_right_line(run):
    with pytest.raises(LichenRuntimeError) as info:
        run('x = 1\nprint(f"{y}")')
    assert info.value.line == 2
    assert "Undefined variable 'y'" in str(info.value)


# =============== running string methods ===============

@pytest.mark.parametrize("source, expected", [
    ('print("Lichen".upper())', "LICHEN"),
    ('print("Lichen".lower())', "lichen"),
    ('print("  padded  ".strip() + "|")', "padded|"),
    ('print("a,b,c".split(","))', '["a", "b", "c"]'),
    ('print("a--b--c".split("--"))', '["a", "b", "c"]'),
    ('print("a b  c".split())', '["a", "b", "c"]'),
    ('print("".split(","))', '[""]'),
    ('print("abc".split("x"))', '["abc"]'),
    ('print(", ".join(["a", "b", "c"]))', "a, b, c"),
    ('print("-".join([]))', ""),
    ('print("-".join(["solo"]))', "solo"),
    ('print("a-b-c".replace("-", "+"))', "a+b+c"),
    ('print("abc".replace("x", "y"))', "abc"),
    ('print("aaa".replace("a", "bb"))', "bbbbbb"),
    ('print("lichen".startswith("lic"), "lichen".startswith("x"))', "true false"),
    ('print("lichen".endswith("hen"), "lichen".endswith("x"))', "true false"),
    ('print("  Hi  ".strip().upper())', "HI"),
    ('words = "the quick fox".split(" ")\nprint(words[1].upper())', "QUICK"),
    ('print(",".join("a b c".split(" ")))', "a,b,c"),
    ('s = "hi"\nprint(s.upper(), s)', "HI hi"),
])
def test_string_methods(run, source, expected):
    assert out(run, source) == expected


def test_strings_are_not_changed_by_methods(run):
    assert out(run, 's = "abc"\nt = s.upper()\nprint(s, t)') == "abc ABC"


def test_methods_in_a_loop_building_a_list(run):
    src = (
        'shout = []\n'
        'for w in "a b c".split(" ") {\n  push(shout, w.upper())\n}\n'
        'print(", ".join(shout))'
    )
    assert out(run, src) == "A, B, C"


def test_fstring_with_methods_inside(run):
    src = 'words = ["a", "b"]\nprint(f"{", ".join(words)} ({len(words)} words)")'
    assert out(run, src) == "a, b (2 words)"


@pytest.mark.parametrize("source, message", [
    ('"a".nope()', "A string has no method 'nope'"),
    ("x = 5\nx.upper()", "A number has no method 'upper'"),
    ("[1].upper()", "A list has no method 'upper'"),
    ('{"a": 1}.upper()', "A dictionary has no method 'upper'"),
    ('"a".upper(1)', "upper() takes no arguments but got 1"),
    ('"a".replace("a")', "replace() takes 2 argument(s) but got 1"),
    ('"a".split(1, 2)', "split() takes 0 or 1 arguments but got 2"),
    ('"a".join()', "join() takes 1 argument(s) but got 0"),
    ('"a".split(1)', "split() needs a string, got number"),
    ('"a".split("")', "split() separator can't be empty"),
    ('",".join("abc")', "join() needs a list, got string"),
    ('",".join([1, 2])', "join() needs a list of strings, but item 0 is a number"),
    ('",".join(["a", 2])', "join() needs a list of strings, but item 1 is a number"),
    ('"a".replace("", "x")', "replace() can't search for an empty string"),
    ('"a".replace(1, "x")', "replace() needs a string, got number"),
    ('"a".startswith(1)', "startswith() needs a string, got number"),
    ('"a".endswith([1])', "endswith() needs a string, got list"),
])
def test_method_errors(run, source, message):
    with pytest.raises(LichenRuntimeError, match=re.escape(message)):
        run(source)


def test_method_error_reports_its_line(run):
    with pytest.raises(LichenRuntimeError) as info:
        run('x = 1\ny = "a"\ny.nope()')
    assert info.value.line == 3
