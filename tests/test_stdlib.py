import re

import pytest

from lichen.evaluator import LichenRuntimeError


def out(run, source):
    return run(source).rstrip("\n")


# =============== min and max ===============

@pytest.mark.parametrize("source, expected", [
    ("print(min(3, 1, 2))", "1"),
    ("print(max(3, 1, 2))", "3"),
    ("print(min([4, 2, 9]))", "2"),
    ("print(max([4, 2, 9]))", "9"),
    ("print(min(5, 7))", "5"),
    ("print(max(-5, -7))", "-5"),
    ("print(min([-3, 0, 3]))", "-3"),
    ("print(max([7]))", "7"),
    ("print(max(1, 2.5))", "2.5"),
    ("print(min(2.5, 1))", "1"),
    ('print(min("b", "a", "c"))', "a"),
    ('print(max(["pear", "apple", "fig"]))', "pear"),
    ('print(min("B", "a"))', "B"),
    ("print(max(range(10)))", "9"),
    ("print(min(1 + 1, 3 - 2))", "1"),
    ('print(max(values({"a": 1, "b": 9})))', "9"),
])
def test_min_and_max(run, source, expected):
    assert out(run, source) == expected


@pytest.mark.parametrize("source, message", [
    ("min([])", "min() can't be given an empty list"),
    ("max([])", "max() can't be given an empty list"),
    ('min(1, "a")', "min() can't compare number and string"),
    ('max("a", 1)', "max() can't compare string and number"),
    ("min([[1], [2]])", "min() can only compare numbers or strings, got list"),
    ("max(true, false)", "max() can only compare numbers or strings, got boolean"),
    ('min({"a": 1}, {"b": 2})', "min() can only compare numbers or strings, got dictionary"),
    ("min(5)", "min() needs a list, or two or more values"),
    ('max("abc")', "max() needs a list, or two or more values"),
    ("min()", "Wrong number of arguments for min()"),
])
def test_min_and_max_errors(run, source, message):
    with pytest.raises(LichenRuntimeError, match=re.escape(message)):
        run(source)


# =============== sum ===============

@pytest.mark.parametrize("source, expected", [
    ("print(sum([1, 2, 3]))", "6"),
    ("print(sum([]))", "0"),
    ("print(sum([7]))", "7"),
    ("print(sum([1.5, 2.5]))", "4.0"),
    ("print(sum([1, 2.5]))", "3.5"),
    ("print(sum([-1, 1, -5]))", "-5"),
    ("print(sum(range(1, 101)))", "5050"),
    ("print(sum([0.1, 0.2]) == 0.1 + 0.2)", "true"),
    ("xs = [2, 4, 6]\nprint(sum(xs) / len(xs))", "4"),
])
def test_sum(run, source, expected):
    assert out(run, source) == expected


@pytest.mark.parametrize("source, message", [
    ("sum(5)", "sum() needs a list, got number"),
    ('sum("abc")', "sum() needs a list, got string"),
    ('sum([1, "a"])', "sum() needs a list of numbers, but item 1 is a string"),
    ("sum([true])", "sum() needs a list of numbers, but item 0 is a boolean"),
    ("sum([[1]])", "sum() needs a list of numbers, but item 0 is a list"),
    ("sum(1, 2)", "Wrong number of arguments for sum()"),
])
def test_sum_errors(run, source, message):
    with pytest.raises(LichenRuntimeError, match=re.escape(message)):
        run(source)


# =============== abs ===============

@pytest.mark.parametrize("source, expected", [
    ("print(abs(-5))", "5"),
    ("print(abs(5))", "5"),
    ("print(abs(0))", "0"),
    ("print(abs(-2.5))", "2.5"),
    ("print(abs(3 - 10))", "7"),
])
def test_abs(run, source, expected):
    assert out(run, source) == expected


@pytest.mark.parametrize("source, message", [
    ('abs("x")', "abs() needs a number, got string"),
    ("abs(true)", "abs() needs a number, got boolean"),
    ("abs([1])", "abs() needs a number, got list"),
    ("abs()", "Wrong number of arguments for abs()"),
])
def test_abs_errors(run, source, message):
    with pytest.raises(LichenRuntimeError, match=re.escape(message)):
        run(source)


# =============== round ===============

@pytest.mark.parametrize("source, expected", [
    ("print(round(2.4))", "2"),
    ("print(round(2.6))", "3"),
    ("print(round(2.5))", "2"),     # halves go to the nearest even number, like Python
    ("print(round(3.5))", "4"),
    ("print(round(-2.5))", "-2"),
    ("print(round(-2.6))", "-3"),
    ("print(round(7))", "7"),
    ("print(round(0.4))", "0"),
    ("print(round(3.14159, 2))", "3.14"),
    ("print(round(2.567, 1))", "2.6"),
    ("print(round(5, 2))", "5"),
    ("print(round(1234, -2))", "1200"),
    ("print(round(2.5, 0))", "2.0"),
    ("print(round(10 / 3, 3))", "3.333"),
])
def test_round(run, source, expected):
    assert out(run, source) == expected


def test_round_without_digits_gives_a_whole_number(run):
    assert out(run, "print(type(round(2.7)), round(2.7) + 1)") == "number 4"


@pytest.mark.parametrize("source, message", [
    ('round("x")', "round() needs a number, got string"),
    ("round(true)", "round() needs a number, got boolean"),
    ("round(1.5, 1.5)", "round() digits must be a whole number"),
    ('round(1.5, "a")', "round() digits must be a whole number"),
    ("round(1.5, true)", "round() digits must be a whole number"),
    ("round()", "Wrong number of arguments for round()"),
    ("round(1, 2, 3)", "Wrong number of arguments for round()"),
])
def test_round_errors(run, source, message):
    with pytest.raises(LichenRuntimeError, match=re.escape(message)):
        run(source)


# =============== sort ===============

@pytest.mark.parametrize("source, expected", [
    ("print(sort([3, 1, 2]))", "[1, 2, 3]"),
    ("print(sort([]))", "[]"),
    ("print(sort([5]))", "[5]"),
    ("print(sort([1, 2, 3]))", "[1, 2, 3]"),
    ("print(sort([3, 3, 1, 1]))", "[1, 1, 3, 3]"),
    ("print(sort([-1, -5, 0, 3]))", "[-5, -1, 0, 3]"),
    ("print(sort([2.5, 1, 3, 0.5]))", "[0.5, 1, 2.5, 3]"),
    ('print(sort(["pear", "apple", "fig"]))', '["apple", "fig", "pear"]'),
    ('print(sort(["b", "A", "a", "B"]))', '["A", "B", "a", "b"]'),
    ('print(sort(["10", "9", "1"]))', '["1", "10", "9"]'),
    ("print(sort(range(5, 0, -1)))", "[1, 2, 3, 4, 5]"),
    ('print(sort(keys({"b": 1, "a": 2})))', '["a", "b"]'),
])
def test_sort(run, source, expected):
    assert out(run, source) == expected


def test_sort_returns_a_new_list_and_leaves_the_original_alone(run):
    assert out(run, "xs = [3, 1, 2]\nys = sort(xs)\nprint(xs, ys)") == "[3, 1, 2] [1, 2, 3]"


def test_sorting_a_slice_does_not_touch_the_list(run):
    assert out(run, "xs = [5, 4, 3, 2]\nprint(sort(xs[:2]), xs)") == "[4, 5] [5, 4, 3, 2]"


@pytest.mark.parametrize("source, message", [
    ("sort(5)", "sort() needs a list, got number"),
    ('sort("cba")', "sort() needs a list, got string"),
    ('sort([1, "a"])', "sort() can't compare number and string"),
    ("sort([[2], [1]])", "sort() can only compare numbers or strings, got list"),
    ("sort([true, false])", "sort() can only compare numbers or strings, got boolean"),
    ("sort()", "Wrong number of arguments for sort()"),
])
def test_sort_errors(run, source, message):
    with pytest.raises(LichenRuntimeError, match=re.escape(message)):
        run(source)


# =============== type ===============

@pytest.mark.parametrize("source, expected", [
    ("print(type(1))", "number"),
    ("print(type(2.5))", "number"),
    ('print(type("a"))', "string"),
    ('print(type(f"{1}"))', "string"),
    ("print(type(true))", "boolean"),
    ("print(type([1]))", "list"),
    ("print(type([]))", "list"),
    ('print(type({"a": 1}))', "dictionary"),
    ("print(type({}))", "dictionary"),
    ("print(type(print))", "function"),
    ("print(type(type))", "function"),
    ("fn f() {\n}\nprint(type(f))", "function"),
    ("fn f() {\n}\nprint(type(f()))", "nil"),
    ("print(type(1 < 2))", "boolean"),
    ("print(type(10 / 4), type(10 / 5))", "number number"),
    ('print(type("a"[0]), type([1][0]))', "string number"),
])
def test_type(run, source, expected):
    assert out(run, source) == expected


def test_type_in_a_condition(run):
    src = (
        'for x in [1, "a", [1]] {\n'
        '  if type(x) == "list" {\n    print("a list")\n  } else {\n    print("not a list")\n  }\n'
        "}"
    )
    assert out(run, src) == "not a list\nnot a list\na list"


@pytest.mark.parametrize("source, message", [
    ("type()", "Wrong number of arguments for type()"),
    ("type(1, 2)", "Wrong number of arguments for type()"),
])
def test_type_errors(run, source, message):
    with pytest.raises(LichenRuntimeError, match=re.escape(message)):
        run(source)


# =============== working together ===============

def test_average_rounded(run):
    src = "scores = [88, 92.5, 79, 95, 61]\nprint(round(sum(scores) / len(scores), 1))"
    assert out(run, src) == "83.1"


def test_sorted_words_joined(run):
    assert out(run, 'print(", ".join(sort(["pear", "apple", "fig"])))') == "apple, fig, pear"


def test_largest_and_smallest_in_an_fstring(run):
    src = "xs = [4, 8, 15]\nprint(f\"{min(xs)} to {max(xs)}, total {sum(xs)}\")"
    assert out(run, src) == "4 to 15, total 27"


def test_median_of_a_list(run):
    src = (
        "fn median(xs) {\n"
        "  s = sort(xs)\n"
        "  mid = len(s) / 2\n"
        "  if len(s) % 2 == 1 {\n    return s[round(mid - 0.5)]\n  }\n"
        "  return (s[mid - 1] + s[mid]) / 2\n"
        "}\n"
        "print(median([5, 1, 3]), median([4, 1, 3, 2]))"
    )
    assert out(run, src) == "3 2.5"


def test_errors_from_the_library_can_be_caught(run):
    src = 'try {\n  min([])\n} except e {\n  print(e)\n}'
    assert out(run, src) == "min() can't be given an empty list"


def test_errors_report_the_right_line(run):
    with pytest.raises(LichenRuntimeError) as info:
        run("x = 1\ny = 2\nprint(sum(5))")
    assert info.value.line == 3


def test_builtins_print_as_builtins(run):
    assert out(run, "print(min, type)") == "<builtin min> <builtin type>"


# ---- these are ordinary names, so programs can still use them ----

def test_a_variable_can_shadow_a_library_function(run):
    with pytest.raises(LichenRuntimeError, match="Can't call a number"):
        run("sum = 5\nprint(sum([1, 2]))")


def test_a_function_parameter_can_use_a_library_name(run):
    assert out(run, "fn f(max) {\n  return max * 2\n}\nprint(f(4), max(1, 2))") == "8 2"


def test_a_local_variable_does_not_disturb_the_global_function(run):
    src = "fn f() {\n  sum = 10\n  return sum\n}\nprint(f(), sum([1, 2]))"
    assert out(run, src) == "10 3"
