import re

import pytest

from lichen.evaluator import LichenRuntimeError
from lichen.lexer import lex
from lichen.nodes import Throw, Try
from lichen.parser import ParseError, parse


def body(source):
    return parse(lex(source)).body


def out(run, source):
    return run(source).rstrip("\n")


@pytest.mark.parametrize("word", ["try", "except", "throw"])
def test_new_keywords(word):
    assert lex(word)[0].type == word


# =============== parser ===============

def test_try_node():
    stmt = body("try {\n  x = 1\n} except err {\n  y = 2\n}")[0]
    assert isinstance(stmt, Try)
    assert stmt.name == "err"
    assert len(stmt.body) == 1 and len(stmt.handler) == 1


def test_except_name_is_optional():
    assert body("try {\n} except {\n}")[0].name is None


def test_except_may_start_on_the_next_line():
    assert body("try {\n}\nexcept e {\n}")[0].name == "e"


def test_throw_node():
    stmt = body('throw "boom"')[0]
    assert isinstance(stmt, Throw)


def test_try_blocks_can_nest():
    stmt = body("try {\n  try {\n  } except a {\n  }\n} except b {\n}")[0]
    assert isinstance(stmt.body[0], Try)


def test_break_inside_try_inside_a_loop_is_fine():
    body("while true {\n  try {\n    break\n  } except e {\n  }\n}")


def test_break_inside_try_outside_a_loop_is_still_an_error():
    with pytest.raises(ParseError, match="'break' outside of a loop"):
        parse(lex("try {\n  break\n} except e {\n}"))


@pytest.mark.parametrize("source, message", [
    ("try {\n  x = 1\n}\nprint(1)", "Expected 'except' after the try block (the 'try' on line 1)"),
    ("try {\n  x = 1\n}", "Expected 'except' after the try block"),
    ("try x = 1", "Expected '{'"),
    ("try {\n} except e", "Expected '{'"),
    ("except e {\n}", "Expected an expression, got 'except'"),
    ("throw", "Expected an expression, got end of line"),
])
def test_try_parse_errors(source, message):
    with pytest.raises(ParseError, match=re.escape(message)):
        parse(lex(source))


# =============== running ===============

def test_try_runs_normally_when_nothing_goes_wrong(run):
    src = 'try {\n  print("fine")\n} except e {\n  print("handler")\n}'
    assert out(run, src) == "fine"


def test_a_runtime_error_is_caught(run):
    src = "try {\n  print(1 / 0)\n} except err {\n  print(\"caught:\", err)\n}"
    assert out(run, src) == "caught: Division by zero"


def test_code_after_the_error_in_the_try_block_is_skipped(run):
    src = 'try {\n  print("a")\n  x = 1 / 0\n  print("b")\n} except e {\n  print("c")\n}\nprint("d")'
    assert out(run, src) == "a\nc\nd"


@pytest.mark.parametrize("source, message", [
    ("print(nope)", "Undefined variable 'nope'"),
    ("x = [1, 2][5]", "Index 5 is out of range (length 2)"),
    ('x = {"a": 1}["b"]', 'Key "b" not found'),
    ('x = "a" + 1', "Can't add string and number (try str(...))"),
    ('x = int("abc")', 'Can\'t convert "abc" to an int'),
    ("x = 5 % 0", "Modulo by zero"),
    ('x = "a".nope()', "A string has no method 'nope'"),
    ("const c = 1\nc = 2", "Cannot reassign constant 'c'"),
    ("fn f(a) {\n  return a\n}\nx = f(1, 2)", "f() takes 1 argument(s) but got 2"),
    ("x = f", "Undefined variable 'f'"),
])
def test_all_sorts_of_errors_can_be_caught(run, source, message):
    wrapped = "try {\n" + source + "\n} except e {\n  print(e)\n}"
    assert out(run, wrapped) == message


def test_the_message_does_not_include_the_line_number(run):
    src = "try {\n  x = 1 / 0\n} except e {\n  print(e)\n}"
    assert "(line" not in out(run, src)


def test_errors_from_inside_called_functions_are_caught(run):
    src = "fn a() {\n  return b()\n}\nfn b() {\n  return [1][3]\n}\ntry {\n  a()\n} except e {\n  print(e)\n}"
    assert out(run, src) == "Index 3 is out of range (length 1)"


def test_runaway_recursion_can_be_caught(run):
    src = "fn f(n) {\n  return f(n + 1)\n}\ntry {\n  f(0)\n} except e {\n  print(e)\n}"
    assert out(run, src) == "Stack overflow (too much recursion)"


def test_except_without_a_name(run):
    assert out(run, 'try {\n  throw "x"\n} except {\n  print("caught")\n}') == "caught"


def test_except_on_the_next_line(run):
    assert out(run, 'try {\n  throw "a"\n}\nexcept e {\n  print(e)\n}') == "a"


def test_the_error_variable_stays_around_afterwards(run):
    assert out(run, 'try {\n  throw "kept"\n} except err {\n}\nprint(err)') == "kept"


# ---- throw ----

def test_throw_a_string(run):
    assert out(run, 'try {\n  throw "my error"\n} except e {\n  print(e)\n}') == "my error"


def test_throw_converts_other_values_to_text(run):
    assert out(run, "try {\n  throw 42\n} except e {\n  print(e, e == \"42\")\n}") == "42 true"
    assert out(run, "try {\n  throw [1, 2]\n} except e {\n  print(e)\n}") == "[1, 2]"


def test_throw_with_an_fstring(run):
    src = 'n = 7\ntry {\n  throw f"bad value: {n}"\n} except e {\n  print(e)\n}'
    assert out(run, src) == "bad value: 7"


def test_validation_example(run):
    src = (
        "fn parse_age(s) {\n"
        "  n = int(s)\n"
        "  if n < 0 {\n    throw \"age can't be negative\"\n  }\n"
        "  return n\n"
        "}\n"
        'for text in ["30", "-4", "abc"] {\n'
        "  try {\n    print(parse_age(text))\n  } except e {\n    print(\"error:\", e)\n  }\n"
        "}"
    )
    assert out(run, src) == "30\nerror: age can't be negative\nerror: Can't convert \"abc\" to an int"


def test_an_uncaught_throw_is_a_runtime_error_with_a_line(run):
    with pytest.raises(LichenRuntimeError) as info:
        run('x = 1\nthrow "boom"')
    assert info.value.message == "boom"
    assert info.value.line == 2
    assert str(info.value) == "boom (line 2)"


def test_rethrowing_from_a_handler(run):
    src = (
        "try {\n"
        '  try {\n    throw "inner"\n  } except e {\n    throw f"outer({e})"\n  }\n'
        "} except e {\n  print(e)\n}"
    )
    assert out(run, src) == "outer(inner)"


def test_an_error_inside_the_handler_is_not_swallowed(run):
    with pytest.raises(LichenRuntimeError, match="Undefined variable 'nope'"):
        run('try {\n  throw "a"\n} except e {\n  print(nope)\n}')


def test_nested_try_catches_in_the_innermost_handler(run):
    src = (
        "try {\n"
        '  try {\n    throw "inner"\n  } except e {\n    print("got", e)\n  }\n'
        '  print("outer body continues")\n'
        "} except e {\n  print(\"never\")\n}"
    )
    assert out(run, src) == "got inner\nouter body continues"


# ---- control flow passes straight through try ----

def test_break_inside_try(run):
    src = "for i in range(5) {\n  try {\n    if i == 2 {\n      break\n    }\n    print(i)\n  } except e {\n    print(\"x\")\n  }\n}"
    assert out(run, src) == "0\n1"


def test_continue_inside_try(run):
    src = "for i in range(4) {\n  try {\n    if i % 2 == 0 {\n      continue\n    }\n    print(i)\n  } except e {\n    print(\"x\")\n  }\n}"
    assert out(run, src) == "1\n3"


def test_return_from_inside_try(run):
    src = 'fn f() {\n  try {\n    return "from try"\n  } except e {\n    return "handler"\n  }\n}\nprint(f())'
    assert out(run, src) == "from try"


def test_return_from_inside_the_handler(run):
    src = 'fn f() {\n  try {\n    throw "x"\n  } except e {\n    return "handler"\n  }\n}\nprint(f())'
    assert out(run, src) == "handler"


def test_try_in_a_loop_keeps_going_after_errors(run):
    src = (
        "results = []\n"
        "for d in [2, 0, 5] {\n"
        "  try {\n    push(results, 10 / d)\n  } except e {\n    push(results, e)\n  }\n"
        "}\n"
        "print(results)"
    )
    assert out(run, src) == '[5, "Division by zero", 2]'


def test_try_together_with_outer(run):
    src = (
        "failures = 0\n"
        "fn attempt(n) {\n"
        "  outer failures\n"
        "  try {\n    return 10 / n\n  } except e {\n    failures++\n    return 0\n  }\n"
        "}\n"
        "attempt(0)\nattempt(2)\nattempt(0)\nprint(failures)"
    )
    assert out(run, src) == "2"


def test_a_name_used_by_except_can_be_a_constant_conflict(run):
    with pytest.raises(LichenRuntimeError, match="Cannot reassign constant 'e'"):
        run('const e = 1\ntry {\n  throw "x"\n} except e {\n}')
