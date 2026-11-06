import io
from contextlib import redirect_stdout

import pytest

from lichen.evaluator import Interpreter
from lichen.lexer import lex
from lichen.parser import parse


@pytest.fixture
def run():
    """Run lichen source and return everything it printed."""
    def _run(source, echo=False):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            Interpreter().run(parse(lex(source)), echo=echo)
        return buffer.getvalue()
    return _run
