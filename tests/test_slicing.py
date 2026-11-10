import re

import pytest

from lichen.evaluator import LichenRuntimeError
from lichen.lexer import lex
from lichen.nodes import Index, Name, Num, Slice
from lichen.parser import ParseError, parse


def expr(source):
    return parse(lex("x = " + source)).body[0].value


def out(run, source):
    return run(source).rstrip("\n")


# =============== parser ===============

def test_slice_with_both_ends():
    node = expr("xs[1:3]")
    assert isinstance(node, Slice)
    assert node.start == Num(1) and node.end == Num(3)


def test_slice_with_missing_ends():
    assert expr("xs[:3]").start is None
    assert expr("xs[1:]").end is None
    both = expr("xs[:]")
    assert both.start is None and both.end is None


def test_plain_index_is_still_an_index():
    assert isinstance(expr("xs[1]"), Index)


def test_slice_ends_can_be_expressions():
    node = expr("xs[a + 1:len(xs) - 1]")
    assert node.start.op == "+" and node.end.op == "-"


def test_slice_can_span_lines():
    assert isinstance(expr("xs[\n  1:\n  3\n]"), Slice)


def test_slices_chain_with_indexes_and_methods():
    assert isinstance(expr("xs[1:][0]"), Index)
    assert type(expr('"abc"[1:].upper()')).__name__ == "MethodCall"


@pytest.mark.parametrize("source, message", [
    ("n[0:2] = [9]", "Can't assign to a slice"),
    ("n[1:] = 5", "Can't assign to a slice"),
    ("print([1][])", "Expected an expression, got ']'"),
    ("print([1, 2, 3][::2])", "Expected an expression, got ':'"),
    ("print([1, 2, 3][1:2:3])", "Expected ']'"),
])
def test_slice_parse_errors(source, message):
    with pytest.raises(ParseError, match=re.escape(message)):
        parse(lex(source))


# =============== running ===============

@pytest.mark.parametrize("source, expected", [
    ("print([10, 20, 30, 40, 50][1:3])", "[20, 30]"),
    ("print([10, 20, 30, 40, 50][:2])", "[10, 20]"),
    ("print([10, 20, 30, 40, 50][2:])", "[30, 40, 50]"),
    ("print([10, 20, 30, 40, 50][:])", "[10, 20, 30, 40, 50]"),
    ("print([10, 20, 30, 40, 50][-2:])", "[40, 50]"),
    ("print([10, 20, 30, 40, 50][:-1])", "[10, 20, 30, 40]"),
    ("print([10, 20, 30, 40, 50][-3:-1])", "[30, 40]"),
    ("print([1, 2, 3][1:1])", "[]"),
    ('print("lichen"[1:4])', "ich"),
    ('print("lichen"[:3])', "lic"),
    ('print("lichen"[-3:])', "hen"),
    ('print("lichen"[:])', "lichen"),
    ('print("lichen"[2:3])', "c"),
])
def test_slices(run, source, expected):
    assert out(run, source) == expected


@pytest.mark.parametrize("source, expected", [
    ("print([1, 2, 3][10:])", "[]"),            # past the end
    ("print([1, 2, 3][:10])", "[1, 2, 3]"),     # end clamps
    ("print([1, 2, 3][-10:])", "[1, 2, 3]"),    # start clamps
    ("print([1, 2, 3][3:1])", "[]"),            # start after end
    ("print([][0:5])", "[]"),
    ('print("abc"[5:])', ""),
    ('print("abc"[:99])', "abc"),
    ('print(""[0:1])', ""),
])
def test_out_of_range_slices_are_clamped_not_errors(run, source, expected):
    assert out(run, source) == expected


def test_slice_with_variables_and_expressions(run):
    src = "n = [1, 2, 3, 4, 5]\ni = 1\nprint(n[i:len(n) - 1], n[i + 1:])"
    assert out(run, src) == "[2, 3, 4] [3, 4, 5]"


def test_a_slice_is_a_copy(run):
    assert out(run, "a = [1, 2]\nb = a[:]\nb[0] = 9\nprint(a, b)") == "[1, 2] [9, 2]"


def test_the_copy_is_shallow(run):
    assert out(run, "a = [[1]]\nb = a[:]\nb[0][0] = 5\nprint(a)") == "[[5]]"


def test_slicing_a_slice(run):
    assert out(run, "print([1, 2, 3, 4, 5][1:][1:3])") == "[3, 4]"


def test_slice_then_method_and_fstring(run):
    assert out(run, 'print("lichen"[:3].upper())') == "LIC"
    assert out(run, 'n = [1, 2, 3]\nprint(f"{n[1:]}")') == "[2, 3]"


def test_reversing_the_first_half_with_a_loop(run):
    src = (
        "xs = [1, 2, 3, 4]\n"
        "head = xs[:2]\n"
        "out = []\n"
        "for i in range(len(head)) {\n  push(out, head[len(head) - 1 - i])\n}\n"
        "print(out)"
    )
    assert out(run, src) == "[2, 1]"


@pytest.mark.parametrize("source, message", [
    ('print({"a": 1}[0:1])', "Can't slice a dictionary"),
    ("x = 5\nprint(x[0:1])", "Can't slice a number"),
    ("print(true[0:1])", "Can't slice a boolean"),
    ("print([1, 2][0.5:1])", "Slice positions must be whole numbers"),
    ('print([1, 2]["a":])', "Slice positions must be whole numbers"),
    ("print([1, 2][:true])", "Slice positions must be whole numbers"),
])
def test_slice_runtime_errors(run, source, message):
    with pytest.raises(LichenRuntimeError, match=re.escape(message)):
        run(source)


def test_slice_error_reports_its_line(run):
    with pytest.raises(LichenRuntimeError) as info:
        run("x = 1\ny = 5\nprint(y[0:1])")
    assert info.value.line == 3
