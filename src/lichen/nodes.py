from dataclasses import dataclass, fields, is_dataclass
from typing import Any, List, Optional


# ---------- expressions ----------

@dataclass
class Num:
    value: Any

@dataclass
class Str:
    value: str

@dataclass
class Bool:
    value: bool

@dataclass
class Name:
    name: str
    line: int = 0

@dataclass
class ListLit:
    items: list

@dataclass
class Unary:
    op: str
    operand: Any
    line: int = 0

@dataclass
class Binary:
    op: str
    left: Any
    right: Any
    line: int = 0

@dataclass
class Call:
    func: Any
    args: list
    line: int = 0

@dataclass
class Index:
    obj: Any
    index: Any
    line: int = 0

@dataclass
class FString:
    parts: list

@dataclass
class MethodCall:
    obj: Any
    name: str
    args: list
    line: int = 0

@dataclass
class Pair:
    key: Any
    value: Any

@dataclass
class DictLit:
    pairs: list


# ---------- statements ----------

@dataclass
class Assign:
    name: str
    value: Any
    const: bool = False
    line: int = 0

@dataclass
class IndexAssign:
    obj: Any
    index: Any
    value: Any
    op: Optional[str] = None
    line: int = 0

@dataclass
class ExprStmt:
    expr: Any

@dataclass
class Return:
    value: Optional[Any]
    line: int = 0

@dataclass
class Break:
    line: int = 0

@dataclass
class Continue:
    line: int = 0

@dataclass
class Branch:
    cond: Any
    body: list

@dataclass
class If:
    branches: list
    else_body: Optional[list] = None

@dataclass
class While:
    cond: Any
    body: list

@dataclass
class For:
    var: str
    iterable: Any
    body: list
    line: int = 0

@dataclass
class FnDef:
    name: str
    params: list
    body: list
    line: int = 0

@dataclass
class Program:
    body: list


def dump(node, indent=0):
    """Pretty-print a tree for debugging."""
    pad = "  " * indent
    if isinstance(node, list):
        if not node:
            return pad + "(empty)"
        return "\n".join(dump(n, indent) for n in node)
    if is_dataclass(node):
        simple, nested = [], []
        for f in fields(node):
            if f.name == "line":
                continue
            v = getattr(node, f.name)
            if is_dataclass(v) or isinstance(v, list):
                nested.append((f.name, v))
            else:
                simple.append(f"{f.name}={v!r}")
        lines = [pad + type(node).__name__ + (" " + " ".join(simple) if simple else "")]
        for name, v in nested:
            lines.append(pad + "  " + name + ":")
            lines.append(dump(v, indent + 2))
        return "\n".join(lines)
    return pad + repr(node)
