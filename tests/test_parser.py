import re

import pytest

from lichen.lexer import lex
from lichen.nodes import (
    Assign, Binary, Break, Continue, ExprStmt, For, FnDef, If, ListLit,
    Name, Num, Return, Unary, While,
)
from lichen.parser import ParseError, parse


def body(source):
    return parse(lex(source)).body


def expr(source):
    """Parse 'x = <source>' and return just the expression."""
    return body("x = " + source)[0].value


def test_multiplication_binds_tighter_than_addition():
    tree = expr("1 + 2 * 3")
    assert tree.op == "+"
    assert tree.left == Num(1)
    assert tree.right.op == "*"


def test_parentheses_override_precedence():
    tree = expr("(1 + 2) * 3")
    assert tree.op == "*"
    assert tree.left.op == "+"


def test_modulo_has_multiplication_precedence():
    tree = expr("2 + 7 % 4")
    assert tree.op == "+"
    assert tree.right.op == "%"


def test_subtraction_is_left_associative():
    tree = expr("10 - 3 - 2")
    assert tree.op == "-"
    assert tree.left.op == "-"
    assert tree.right == Num(2)


def test_unary_minus_and_not():
    assert isinstance(expr("-5"), Unary) and expr("-5").op == "-"
    assert isinstance(expr("not true"), Unary) and expr("not true").op == "not"


def test_and_binds_tighter_than_or():
    tree = expr("a or b and c")
    assert tree.op == "or"
    assert tree.right.op == "and"


def test_comparison_binds_tighter_than_and():
    tree = expr("a < b and c > d")
    assert tree.op == "and"
    assert tree.left.op == "<"


def test_not_in_is_one_operator():
    tree = expr("x not in nums")
    assert tree.op == "not in"


def test_in_operator():
    assert expr("x in nums").op == "in"


def test_list_literal_and_trailing_comma():
    assert isinstance(expr("[1, 2, 3]"), ListLit)
    assert len(expr("[1, 2, 3,]").items) == 3


def test_list_can_span_lines():
    assert len(expr("[\n  1,\n  2,\n]").items) == 2


def test_call_and_index_chain():
    tree = expr("f(1)(2)[0]")
    assert type(tree).__name__ == "Index"
    assert type(tree.obj).__name__ == "Call"


def test_const_flag():
    assert body("const a = 1")[0].const is True
    assert body("a = 1")[0].const is False


def test_increment_becomes_plain_assignment():
    stmt = body("x++")[0]
    assert isinstance(stmt, Assign)
    assert stmt.value.op == "+"
    assert stmt.value.left == Name("x", 1)
    assert stmt.value.right == Num(1)


def test_decrement_and_compound_assignment():
    assert body("x--")[0].value.op == "-"
    stmt = body("x += 5")[0]
    assert stmt.value.op == "+" and stmt.value.right == Num(5)
    assert body("x -= 5")[0].value.op == "-"


def test_if_elif_else_structure():
    stmt = body("if a {\n}\nelif b {\n}\nelse {\n}")[0]
    assert isinstance(stmt, If)
    assert len(stmt.branches) == 2
    assert stmt.else_body == []


def test_else_on_same_line_as_brace():
    stmt = body("if a {\n} else {\n}")[0]
    assert stmt.else_body == []


def test_else_on_next_line_works():
    stmt = body("if a {\n}\nelse {\n}")[0]
    assert stmt.else_body == []


def test_if_without_else():
    assert body("if a {\n}")[0].else_body is None


def test_while_and_for():
    assert isinstance(body("while a {\n}")[0], While)
    loop = body("for i in range(3) {\n}")[0]
    assert isinstance(loop, For) and loop.var == "i"


def test_function_definition():
    fn = body("fn add(a, b) {\n  return a + b\n}")[0]
    assert isinstance(fn, FnDef)
    assert fn.params == ["a", "b"]
    assert isinstance(fn.body[0], Return)


def test_function_with_no_params():
    assert body("fn f() {\n}")[0].params == []


def test_bare_return():
    stmt = body("fn f() {\n  return\n}")[0].body[0]
    assert stmt.value is None


def test_break_and_continue_inside_loops():
    loop = body("while a {\n  break\n  continue\n}")[0]
    assert isinstance(loop.body[0], Break)
    assert isinstance(loop.body[1], Continue)


def test_break_inside_if_inside_loop():
    loop = body("for i in nums {\n  if i {\n    break\n  }\n}")[0]
    assert isinstance(loop.body[0].branches[0].body[0], Break)


def test_function_inside_loop_still_loops_fine():
    # a loop *inside* a function is fine
    body("fn f() {\n  while true {\n    break\n  }\n}")


def test_expression_statement():
    assert isinstance(body("f(1)")[0], ExprStmt)


def test_one_line_block():
    assert isinstance(body("fn f() { return 1 }")[0], FnDef)


@pytest.mark.parametrize("source, message", [
    ("x = (1 + 2", "Expected ')'"),
    ("if x {\n  print(1)\n", "Missing closing '}'"),
    ("x = = 5", "Expected an expression"),
    ("nums = [1 2]", "Expected ']'"),
    ("const = 5", "Expected a name after 'const'"),
    ("x = 5 5", "Expected end of line"),
    ("fn (a) {\n}", "Expected a function name"),
    ("for in x {\n}", "Expected a loop variable name"),
    ("break", "'break' outside of a loop"),
    ("continue", "'continue' outside of a loop"),
    ("if x {\n  break\n}", "'break' outside of a loop"),
    ("for i in nums {\n  fn f() {\n    break\n  }\n}", "'break' outside of a loop"),
])
def test_parse_errors(source, message):
    with pytest.raises(ParseError, match=re.escape(message)):
        parse(lex(source))


def test_parse_error_has_position():
    with pytest.raises(ParseError, match="line 1, col 5"):
        parse(lex("x = = 5"))
