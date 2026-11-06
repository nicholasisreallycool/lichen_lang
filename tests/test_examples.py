import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from lichen.evaluator import Interpreter
from lichen.lexer import lex
from lichen.parser import parse

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.lch"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_runs_without_errors(path):
    source = path.read_text(encoding="utf-8")
    with redirect_stdout(io.StringIO()):
        Interpreter().run(parse(lex(source)))
