import re

import pytest

from lichen.evaluator import LichenRuntimeError
from lichen.lexer import lex
from lichen.parser import parse


def out(run, source):
    return run(source).rstrip("\n")


# ---------- values and operators ----------

@pytest.mark.parametrize("source, expected", [
    ("print(1 + 2 * 3)", "7"),
    ("print((1 + 2) * 3)", "9"),
    ("print(10 - 3 - 2)", "5"),
    ("print(-(1 + 2))", "-3"),
    ("print(10 / 2)", "5"),
    ("print(7 / 2)", "3.5"),
    ("print(1.5 + 1.5)", "3.0"),
    ("print(10 % 3)", "1"),
    ("print(-7 % 3)", "2"),
    ("print(7.5 % 2)", "1.5"),
    ("print(10 % 3 * 2)", "2"),
    ("print(2 + 7 % 4)", "5"),
])
def test_arithmetic(run, source, expected):
    assert out(run, source) == expected


@pytest.mark.parametrize("source, expected", [
    ('print("a" + "b")', "ab"),
    ('print("lichen"[0])', "l"),
    ('print("lichen"[-1])', "n"),
    ('print(len("abc"))', "3"),
    ("print([1, 2] + [3])", "[1, 2, 3]"),
    ('print(["a", 1, true])', '["a", 1, true]'),
    ("print([1, 2, 3][1])", "2"),
    ("print([1, 2, 3][-1])", "3"),
    ("print(len([1, 2]))", "2"),
    ("print([])", "[]"),
])
def test_strings_and_lists(run, source, expected):
    assert out(run, source) == expected


@pytest.mark.parametrize("source, expected", [
    ("print(1 < 2)", "true"),
    ("print(2 <= 2)", "true"),
    ("print(3 > 4)", "false"),
    ('print("a" < "b")', "true"),
    ("print(1 == 1.0)", "true"),
    ('print("a" != "b")', "true"),
    ("print(true == 1)", "false"),
    ("print([1, 2] == [1, 2])", "true"),
    ("print(1 < 2 and not false)", "true"),
    ("print(false or true)", "true"),
    ("print(false and undefined_name)", "false"),
    ("print(true or undefined_name)", "true"),
    ("print(not 0)", "true"),
])
def test_comparison_and_logic(run, source, expected):
    assert out(run, source) == expected


@pytest.mark.parametrize("source, expected", [
    ("print(3 in [1, 2, 3])", "true"),
    ("print(4 in [1, 2, 3])", "false"),
    ("print(4 not in [1, 2, 3])", "true"),
    ('print("ich" in "lichen")', "true"),
    ('print("z" in "lichen")', "false"),
    ('print("z" not in "lichen")', "true"),
    ('print("a" in ["a", "b"])', "true"),
    ("print(not 3 in [3])", "false"),
    ("print(true in [1])", "false"),
])
def test_in_operator(run, source, expected):
    assert out(run, source) == expected


# ---------- built-in functions ----------

@pytest.mark.parametrize("source, expected", [
    ('print(int("42") + 1)', "43"),
    ("print(int(3.9))", "3"),
    ('print(float("2.5"))', "2.5"),
    ("print(str(5) + \"!\")", "5!"),
    ("print(range(3))", "[0, 1, 2]"),
    ("print(range(1, 4))", "[1, 2, 3]"),
    ("print(range(0, 10, 5))", "[0, 5]"),
    ("print(range(0))", "[]"),
    ("print(1, \"two\", [3])", '1 two [3]'),
    ("a = [1]\npush(a, 2)\nprint(a)", "[1, 2]"),
    ("print(true, false)", "true false"),
])
def test_builtins(run, source, expected):
    assert out(run, source) == expected


# ---------- variables and constants ----------

def test_assignment_and_update(run):
    assert out(run, "x = 5\nx += 2\nx++\nx--\nx -= 1\nprint(x)") == "6"


def test_const_can_be_read(run):
    assert out(run, "const a = 5\nprint(a * 2)") == "10"


def test_loop_variable_persists_after_loop(run):
    assert out(run, "for i in range(3) {\n}\nprint(i)") == "2"


# ---------- control flow ----------

@pytest.mark.parametrize("n, expected", [(5, "big"), (3, "three"), (1, "small")])
def test_if_elif_else(run, n, expected):
    source = (
        f"x = {n}\n"
        'if x > 3 {\n  print("big")\n}\n'
        'elif x == 3 {\n  print("three")\n}\n'
        'else {\n  print("small")\n}'
    )
    assert out(run, source) == expected


def test_while_loop(run):
    assert out(run, "x = 3\nwhile x > 0 {\n  print(x)\n  x--\n}") == "3\n2\n1"


def test_for_over_list_and_string(run):
    assert out(run, "for n in [1, 2] {\n  print(n)\n}") == "1\n2"
    assert out(run, 'for c in "ab" {\n  print(c)\n}') == "a\nb"


def test_for_over_a_copy_so_changes_are_safe(run):
    assert out(run, "a = [1, 2]\nfor n in a {\n  push(a, n)\n}\nprint(a)") == "[1, 2, 1, 2]"


def test_break_in_for(run):
    assert out(run, "for n in range(10) {\n  if n == 3 {\n    break\n  }\n  print(n)\n}") == "0\n1\n2"


def test_continue_in_for(run):
    src = "for n in range(5) {\n  if n % 2 == 0 {\n    continue\n  }\n  print(n)\n}"
    assert out(run, src) == "1\n3"


def test_break_in_while_true(run):
    assert out(run, "i = 0\nwhile true {\n  i++\n  if i == 4 {\n    break\n  }\n}\nprint(i)") == "4"


def test_continue_in_while(run):
    src = "i = 0\nwhile i < 5 {\n  i++\n  if i % 2 == 0 {\n    continue\n  }\n  print(i)\n}"
    assert out(run, src) == "1\n3\n5"


def test_break_only_exits_the_inner_loop(run):
    src = (
        "for a in range(2) {\n"
        "  for b in range(3) {\n"
        "    if b == 1 {\n      break\n    }\n"
        "    print(a, b)\n"
        "  }\n"
        "}"
    )
    assert out(run, src) == "0 0\n1 0"


def test_fizzbuzz(run):
    src = (
        "for i in range(1, 16) {\n"
        '  if i % 15 == 0 {\n    print("FizzBuzz")\n  }\n'
        '  elif i % 3 == 0 {\n    print("Fizz")\n  }\n'
        '  elif i % 5 == 0 {\n    print("Buzz")\n  }\n'
        "  else {\n    print(i)\n  }\n"
        "}"
    )
    expected = "1 2 Fizz 4 Buzz Fizz 7 8 Fizz Buzz 11 Fizz 13 14 FizzBuzz".split()
    assert out(run, src).split("\n") == expected


# ---------- functions and scope ----------

def test_function_call_and_return(run):
    assert out(run, "fn add(a, b) {\n  return a + b\n}\nprint(add(2, 3))") == "5"


def test_function_without_return_gives_nil(run):
    assert out(run, "fn f() {\n}\nprint(f())") == "nil"


def test_bare_return_gives_nil(run):
    assert out(run, "fn f() {\n  return\n}\nprint(f())") == "nil"


def test_early_return(run):
    src = "fn f(n) {\n  if n > 0 {\n    return \"pos\"\n  }\n  return \"neg\"\n}\nprint(f(1), f(-1))"
    assert out(run, src) == "pos neg"


def test_recursion(run):
    src = "fn fib(n) {\n  if n < 2 {\n    return n\n  }\n  return fib(n - 1) + fib(n - 2)\n}\nprint(fib(10))"
    assert out(run, src) == "55"


def test_function_reads_globals(run):
    assert out(run, "g = 5\nfn f() {\n  return g * 2\n}\nprint(f())") == "10"


def test_assignment_in_function_is_local(run):
    src = "x = 10\nfn f() {\n  x = 99\n  return x\n}\nprint(f(), x)"
    assert out(run, src) == "99 10"


def test_closures_remember_their_variables(run):
    src = (
        "fn adder(n) {\n"
        "  fn add(m) {\n    return n + m\n  }\n"
        "  return add\n"
        "}\n"
        "print(adder(5)(3))"
    )
    assert out(run, src) == "8"


def test_functions_are_values(run):
    assert out(run, "fn f() {\n  return 1\n}\ng = f\nprint(g())") == "1"


def test_const_can_be_shadowed_inside_a_function(run):
    src = "const a = 1\nfn f() {\n  a = 2\n  return a\n}\nprint(f(), a)"
    assert out(run, src) == "2 1"


def test_loop_inside_function(run):
    src = "fn total(n) {\n  t = 0\n  for i in range(n) {\n    t += i\n  }\n  return t\n}\nprint(total(5))"
    assert out(run, src) == "10"


# ---------- the REPL echo ----------

def test_echo_prints_bare_expressions(run):
    assert run("2 + 3 * 4", echo=True) == "14\n"


def test_echo_quotes_strings(run):
    assert run('"hi"', echo=True) == '"hi"\n'


def test_echo_skips_nil_and_assignments(run):
    assert run("x = 5\nprint(1)", echo=True) == "1\n"


# ---------- runtime errors ----------

@pytest.mark.parametrize("source, message", [
    ("print(y)", "Undefined variable 'y'"),
    ("const a = 1\na = 2", "Cannot reassign constant 'a'"),
    ("const a = 1\na++", "Cannot reassign constant 'a'"),
    ("const a = 1\nfor a in [1] {\n}", "Cannot reassign constant 'a'"),
    ("print(1 / 0)", "Division by zero"),
    ("print(5 % 0)", "Modulo by zero"),
    ("fn f(a) {\n  return a\n}\nf(1, 2)", "f() takes 1 argument(s) but got 2"),
    ("print(len())", "Wrong number of arguments for len()"),
    ('print("a" + 1)', "Can't add string and number (try str(...))"),
    ("print(true + 1)", "Can't add boolean and number"),
    ("print(1 < \"a\")", "Can't compare number and string"),
    ('print("a" * 2)', "Can't use '*' on string and number"),
    ('print(-"a")', "Can't negate a string"),
    ("x = 5\nx()", "Can't call a number"),
    ("n = [1, 2]\nprint(n[5])", "Index 5 is out of range (length 2)"),
    ("print(5[0])", "Can't index a number"),
    ('print([1][true])', "Index must be a whole number"),
    ("print(1 in 5)", "Can't use 'in' with a number on the right"),
    ('print(1 in "abc")', "Can only look for a string inside a string"),
    ("print(len(5))", "len() needs a string or list"),
    ('print(int("abc"))', "Can't convert"),
    ("print(range(1.5))", "range() only takes whole numbers"),
    ("print(range(1, 5, 0))", "range() step can't be 0"),
    ("push(5, 1)", "push() needs a list"),
    ("for x in 5 {\n}", "Can't loop over a number"),
    ("return 5", "'return' outside of a function"),
])
def test_runtime_errors(run, source, message):
    with pytest.raises(LichenRuntimeError, match=re.escape(message)):
        run(source)


def test_error_reports_the_right_line(run):
    with pytest.raises(LichenRuntimeError) as info:
        run("x = 1\nprint(y)")
    assert info.value.line == 2
    assert "line 2" in str(info.value)


def test_error_inside_a_function_reports_its_own_line(run):
    with pytest.raises(LichenRuntimeError) as info:
        run("fn f() {\n  return nope\n}\nf()")
    assert info.value.line == 2


def test_runaway_recursion_is_a_clean_error(run):
    with pytest.raises(LichenRuntimeError, match="Stack overflow"):
        run("fn f(n) {\n  return f(n + 1)\n}\nf(0)")
