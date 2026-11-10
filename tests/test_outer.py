import re

import pytest

from lichen.evaluator import LichenRuntimeError
from lichen.lexer import lex
from lichen.nodes import Outer
from lichen.parser import ParseError, parse


def body(source):
    return parse(lex(source)).body


def out(run, source):
    return run(source).rstrip("\n")


def test_outer_is_a_keyword():
    assert lex("outer")[0].type == "outer"


# =============== parser ===============

def test_outer_statement_node():
    stmt = body("fn f() {\n  outer count\n}")[0].body[0]
    assert isinstance(stmt, Outer)
    assert stmt.names == ["count"]


def test_outer_with_several_names():
    stmt = body("fn f() {\n  outer a, b, c\n}")[0].body[0]
    assert stmt.names == ["a", "b", "c"]


def test_outer_is_allowed_in_nested_functions_and_blocks():
    body("fn f() {\n  fn g() {\n    outer x\n  }\n}")
    body("fn f() {\n  if true {\n    outer x\n  }\n}")
    body("fn f() {\n  while true {\n    outer x\n    break\n  }\n}")


@pytest.mark.parametrize("source, message", [
    ("outer x", "'outer' can only be used inside a function"),
    ("if true {\n  outer x\n}", "'outer' can only be used inside a function"),
    ("fn f() {\n  outer\n}", "Expected a variable name after 'outer'"),
    ("fn f() {\n  outer a,\n}", "Expected a variable name"),
    ("fn f() {\n  outer 5\n}", "Expected a variable name after 'outer'"),
])
def test_outer_parse_errors(source, message):
    with pytest.raises(ParseError, match=re.escape(message)):
        parse(lex(source))


def test_outer_error_points_at_the_keyword():
    with pytest.raises(ParseError, match="line 2, col 3"):
        parse(lex("x = 1\n  outer x"))


# =============== running ===============

def test_without_outer_assignment_is_still_local(run):
    assert out(run, "n = 0\nfn f() {\n  n++\n}\nf()\nprint(n)") == "0"


def test_outer_changes_a_global(run):
    src = "count = 0\nfn bump() {\n  outer count\n  count++\n}\nbump()\nbump()\nprint(count)"
    assert out(run, src) == "2"


def test_outer_supports_every_assignment_form(run):
    src = (
        "n = 10\n"
        "fn f() {\n  outer n\n  n += 5\n  n -= 1\n  n--\n  n = n * 2\n}\n"
        "f()\nprint(n)"
    )
    assert out(run, src) == "26"


def test_outer_with_several_names(run):
    src = "a = 1\nb = 2\nfn f() {\n  outer a, b\n  a++\n  b += 10\n}\nf()\nprint(a, b)"
    assert out(run, src) == "2 12"


def test_outer_reads_see_the_current_value(run):
    src = "a = 5\nfn f() {\n  outer a\n  a = a + 1\n  return a * 2\n}\nprint(f(), a)"
    assert out(run, src) == "12 6"


def test_outer_reaches_an_enclosing_function(run):
    src = (
        "fn make() {\n"
        "  total = 0\n"
        "  fn add(n) {\n    outer total\n    total += n\n  }\n"
        "  add(5)\n  add(7)\n"
        "  return total\n"
        "}\n"
        "print(make())"
    )
    assert out(run, src) == "12"


def test_outer_skips_over_a_function_that_also_uses_outer(run):
    src = (
        "x = 1\n"
        "fn a() {\n"
        "  outer x\n"
        "  fn b() {\n    outer x\n    x += 10\n  }\n"
        "  b()\n  x += 100\n"
        "}\n"
        "a()\nprint(x)"
    )
    assert out(run, src) == "111"


def test_counter_closure_pattern(run):
    src = (
        "fn make_counter() {\n"
        "  n = 0\n"
        "  fn next() {\n    outer n\n    n++\n    return n\n  }\n"
        "  return next\n"
        "}\n"
        "c = make_counter()\n"
        "d = make_counter()\n"
        "print(c(), c(), c(), d())"
    )
    assert out(run, src) == "1 2 3 1"


def test_outer_inside_loops_and_ifs(run):
    src = (
        "n = 0\n"
        "fn f() {\n  outer n\n  for i in range(4) {\n    if i % 2 == 0 {\n      n += i\n    }\n  }\n}\n"
        "f()\nprint(n)"
    )
    assert out(run, src) == "2"


def test_outer_redirects_a_loop_variable(run):
    src = "i = 0\nfn f() {\n  outer i\n  for i in range(3) {\n  }\n}\nf()\nprint(i)"
    assert out(run, src) == "2"


def test_outer_can_name_a_variable_created_before_the_call(run):
    src = "fn f() {\n  outer late\n  late = 5\n}\nlate = 1\nf()\nprint(late)"
    assert out(run, src) == "5"


def test_each_call_starts_fresh(run):
    src = (
        "n = 0\n"
        "fn f() {\n  outer n\n  n++\n}\n"
        "f()\nf()\nf()\nprint(n)"
    )
    assert out(run, src) == "3"


def test_recursion_with_an_outer_counter(run):
    src = (
        "calls = 0\n"
        "fn fib(n) {\n  outer calls\n  calls++\n  if n < 2 {\n    return n\n  }\n"
        "  return fib(n - 1) + fib(n - 2)\n}\n"
        "print(fib(10), calls)"
    )
    assert out(run, src) == "55 177"


def test_lists_never_needed_outer_to_be_changed_in_place(run):
    src = "xs = [1]\nfn f() {\n  xs[0] = 99\n  push(xs, 2)\n}\nf()\nprint(xs)"
    assert out(run, src) == "[99, 2]"


@pytest.mark.parametrize("source, message", [
    ("fn f() {\n  outer nope\n}\nf()", "There's no variable named 'nope' outside this function"),
    ("x = 1\nfn f() {\n  x = 2\n  outer x\n}\nf()", "'x' is already a local variable here"),
    ("x = 1\nfn f(x) {\n  outer x\n}\nf(2)", "'x' is already a local variable here"),
    ("const x = 1\nfn f() {\n  outer x\n  x = 2\n}\nf()", "Cannot reassign constant 'x'"),
    ("x = 1\nfn f() {\n  outer x\n  const x = 2\n}\nf()", "Can't declare 'x' as a constant"),
])
def test_outer_runtime_errors(run, source, message):
    with pytest.raises(LichenRuntimeError, match=re.escape(message)):
        run(source)


def test_outer_error_reports_its_line(run):
    with pytest.raises(LichenRuntimeError) as info:
        run("fn f() {\n  outer nope\n}\nf()")
    assert info.value.line == 2
