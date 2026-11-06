import re

import pytest

from lichen.evaluator import LichenRuntimeError
from lichen.lexer import lex
from lichen.nodes import DictLit, Index, IndexAssign, Num, Pair, Str
from lichen.parser import ParseError, parse


def body(source):
    return parse(lex(source)).body


def out(run, source):
    return run(source).rstrip("\n")


# =============== parser: assignment targets ===============

def test_index_assignment_node():
    stmt = body("nums[0] = 5")[0]
    assert isinstance(stmt, IndexAssign)
    assert stmt.op is None
    assert stmt.value == Num(5)


def test_compound_index_assignment():
    assert body("nums[0] += 2")[0].op == "+"
    assert body("nums[0] -= 2")[0].op == "-"


def test_increment_on_index():
    stmt = body("nums[0]++")[0]
    assert stmt.op == "+" and stmt.value == Num(1)
    assert body("nums[0]--")[0].op == "-"


def test_nested_index_target():
    stmt = body("grid[1][2] = 7")[0]
    assert isinstance(stmt.obj, Index)


@pytest.mark.parametrize("source", ["f(1) = 2", "5 = 3", "x + 1 = 2", "[1, 2] = 3"])
def test_cannot_assign_to_arbitrary_expressions(source):
    with pytest.raises(ParseError, match="Can't assign to this expression"):
        parse(lex(source))


def test_plain_name_assignment_still_works():
    assert type(body("x = 5")[0]).__name__ == "Assign"


# =============== parser: dictionary literals ===============

def test_empty_dict_literal():
    stmt = body("d = {}")[0]
    assert isinstance(stmt.value, DictLit) and stmt.value.pairs == []


def test_dict_literal_pairs():
    d = body('d = {"a": 1, "b": 2}')[0].value
    assert d.pairs == [Pair(Str("a"), Num(1)), Pair(Str("b"), Num(2))]


def test_dict_literal_trailing_comma_and_multiple_lines():
    d = body('d = {\n  "a": 1,\n  "b": 2,\n}')[0].value
    assert len(d.pairs) == 2


def test_blocks_and_dicts_do_not_confuse_the_parser():
    # a dict right before a block's opening brace
    body('for k in {"a": 1} {\n  print(k)\n}')
    body('if "a" in {"a": 1} {\n  print(1)\n}')
    body("fn f() {\n  return {}\n}")


@pytest.mark.parametrize("source, message", [
    ('d = {"a" 1}', "Expected ':' after a dictionary key"),
    ('d = {"a": 1', "Expected '}'"),
    ('d = {"a": }', "Expected an expression"),
])
def test_dict_parse_errors(source, message):
    with pytest.raises(ParseError, match=re.escape(message)):
        parse(lex(source))


# =============== list item assignment ===============

@pytest.mark.parametrize("source, expected", [
    ("n = [1, 2, 3]\nn[0] = 5\nprint(n)", "[5, 2, 3]"),
    ("n = [1, 2, 3]\nn[-1] = 9\nprint(n)", "[1, 2, 9]"),
    ("n = [1, 2, 3]\nn[1] += 10\nprint(n)", "[1, 12, 3]"),
    ("n = [1, 2, 3]\nn[1] -= 1\nprint(n)", "[1, 1, 3]"),
    ("n = [1, 2, 3]\nn[0]++\nprint(n)", "[2, 2, 3]"),
    ("n = [1, 2, 3]\nn[2]--\nprint(n)", "[1, 2, 2]"),
    ("g = [[1, 2], [3, 4]]\ng[1][0] = 99\nprint(g)", "[[1, 2], [99, 4]]"),
    ("n = [1, 2]\ni = 1\nn[i] = n[0] + 10\nprint(n)", "[1, 11]"),
    ('n = ["a"]\nn[0] += "b"\nprint(n)', '["ab"]'),
])
def test_list_assignment(run, source, expected):
    assert out(run, source) == expected


def test_lists_are_shared_not_copied(run):
    assert out(run, "a = [1]\nb = a\nb[0] = 2\nprint(a)") == "[2]"


def test_functions_can_change_a_list_they_are_given(run):
    src = "fn zero(l) {\n  l[0] = 0\n}\nn = [5, 6]\nzero(n)\nprint(n)"
    assert out(run, src) == "[0, 6]"


def test_const_protects_the_name_not_the_contents(run):
    assert out(run, "const a = [1]\na[0] = 2\nprint(a)") == "[2]"
    with pytest.raises(LichenRuntimeError, match="Cannot reassign constant"):
        run("const a = [1]\na = [2]")


def test_target_is_evaluated_once(run):
    src = (
        "calls = [0]\n"
        "fn pick() {\n  calls[0]++\n  return 0\n}\n"
        "n = [10]\n"
        "n[pick()] += 1\n"
        "print(n, calls[0])"
    )
    assert out(run, src) == "[11] 1"


@pytest.mark.parametrize("source, message", [
    ("n = [1, 2]\nn[5] = 0", "Index 5 is out of range (length 2)"),
    ("n = [1, 2]\nn[-3] = 0", "Index -3 is out of range (length 2)"),
    ("n = [1, 2]\nn[1.5] = 0", "Index must be a whole number"),
    ('n = [1, 2]\nn["a"] = 0', "Index must be a whole number"),
    ('s = "hi"\ns[0] = "x"', "Strings can't be changed"),
    ("x = 5\nx[0] = 1", "Can't assign into a number"),
])
def test_list_assignment_errors(run, source, message):
    with pytest.raises(LichenRuntimeError, match=re.escape(message)):
        run(source)


# =============== dictionaries ===============

@pytest.mark.parametrize("source, expected", [
    ("print({})", "{}"),
    ('print({"a": 1, "b": 2})', '{"a": 1, "b": 2}'),
    ('d = {"name": "lichen"}\nprint(d["name"])', "lichen"),
    ('print({"a": [1, 2], "b": {"c": 3}})', '{"a": [1, 2], "b": {"c": 3}}'),
    ('print({1: "one", 2.5: "x"})', '{1: "one", 2.5: "x"}'),
    ('k = "key"\nprint({k: 1})', '{"key": 1}'),
    ('print({"a": 1 + 2})', '{"a": 3}'),
    ('print({"a": 1} == {"a": 1})', "true"),
    ('print({"a": 1} == {"a": 2})', "false"),
    ('print(len({"a": 1, "b": 2}))', "2"),
    ("print(len({}))", "0"),
    ('print([{"a": 1}])', '[{"a": 1}]'),
])
def test_dictionary_basics(run, source, expected):
    assert out(run, source) == expected


@pytest.mark.parametrize("source, expected", [
    ('d = {}\nd["a"] = 1\nprint(d)', '{"a": 1}'),
    ('d = {"a": 1}\nd["a"] = 5\nprint(d)', '{"a": 5}'),
    ('d = {"a": 1}\nd["a"] += 4\nprint(d)', '{"a": 5}'),
    ('d = {"a": 1}\nd["a"]++\nprint(d["a"])', "2"),
    ('d = {"a": 1}\nd["a"]--\nprint(d["a"])', "0"),
    ('d = {"a": {"b": 1}}\nd["a"]["b"] = 2\nprint(d)', '{"a": {"b": 2}}'),
    ("d = {}\nd[1] = \"x\"\nprint(d[1])", "x"),
    ('d = {"z": 1, "a": 2}\nd["m"] = 3\nprint(d)', '{"z": 1, "a": 2, "m": 3}'),
])
def test_dictionary_assignment(run, source, expected):
    assert out(run, source) == expected


@pytest.mark.parametrize("source, expected", [
    ('print("a" in {"a": 1})', "true"),
    ('print("b" in {"a": 1})', "false"),
    ('print("b" not in {"a": 1})', "true"),
    ('print(1 in {"1": "x"})', "false"),
    ("print([1] in {})", "false"),
    ("print(true in {1: 2})", "false"),
])
def test_in_checks_keys(run, source, expected):
    assert out(run, source) == expected


def test_for_loop_goes_over_keys_in_insertion_order(run):
    assert out(run, 'for k in {"b": 1, "a": 2} {\n  print(k)\n}') == "b\na"


def test_keys_values_remove(run):
    src = (
        'd = {"a": 1, "b": 2, "c": 3}\n'
        "print(keys(d))\n"
        "print(values(d))\n"
        'remove(d, "b")\n'
        "print(d)"
    )
    assert out(run, src) == '["a", "b", "c"]\n[1, 2, 3]\n{"a": 1, "c": 3}'


def test_dictionaries_are_shared_like_lists(run):
    src = 'fn tag(d) {\n  d["seen"] = true\n}\nx = {}\ntag(x)\nprint(x)'
    assert out(run, src) == '{"seen": true}'


def test_word_counter(run):
    src = (
        'words = ["the", "fox", "the", "dog", "the", "fox"]\n'
        "counts = {}\n"
        "for w in words {\n"
        "  if w in counts {\n    counts[w] += 1\n  } else {\n    counts[w] = 1\n  }\n"
        "}\n"
        "print(counts)"
    )
    assert out(run, src) == '{"the": 3, "fox": 2, "dog": 1}'


def test_echo_shows_dictionaries(run):
    assert run('{"a": 1}', echo=True) == '{"a": 1}\n'


@pytest.mark.parametrize("source, message", [
    ('d = {"a": 1}\nprint(d["z"])', 'Key "z" not found'),
    ("print({1: 2}[5])", "Key 5 not found"),
    ('d = {"a": 1}\nd["z"] += 1', 'Key "z" not found'),
    ("d = {[1]: 2}", "Dictionary keys must be strings or numbers, not list"),
    ("d = {true: 1}", "Dictionary keys must be strings or numbers, not boolean"),
    ("d = {}\nd[[1]] = 1", "Dictionary keys must be strings or numbers, not list"),
    ("d = {}\nprint(d[[1]])", "Dictionary keys must be strings or numbers, not list"),
    ('remove({"a": 1}, "b")', 'Key "b" not found'),
    ("remove([1], 0)", "remove() needs a dictionary"),
    ("keys(5)", "keys() needs a dictionary, got number"),
    ("values([1])", "values() needs a dictionary, got list"),
    ("print({} + {})", "Can't add dictionary and dictionary"),
    ("print(len(true))", "len() needs a string, list, or dictionary, got boolean"),
])
def test_dictionary_errors(run, source, message):
    with pytest.raises(LichenRuntimeError, match=re.escape(message)):
        run(source)
