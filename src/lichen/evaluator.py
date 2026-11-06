import sys

from lichen.nodes import ExprStmt


class LichenRuntimeError(Exception):
    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self):
        if self.line:
            return f"{self.message} (line {self.line})"
        return self.message


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class ReturnSignal(Exception):
    def __init__(self, value, line):
        self.value = value
        self.line = line


# ---------- values ----------

class Function:
    def __init__(self, name, params, body, closure):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure


class Builtin:
    def __init__(self, name, func, min_args, max_args):
        self.name = name
        self.func = func
        self.min_args = min_args
        self.max_args = max_args


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def type_name(v):
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "boolean"
    if is_number(v):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "list"
    return "function"


def to_str(v, quote=False):
    if v is None:
        return "nil"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, str):
        return f'"{v}"' if quote else v
    if isinstance(v, list):
        return "[" + ", ".join(to_str(x, True) for x in v) + "]"
    if isinstance(v, Function):
        return f"<fn {v.name}>"
    if isinstance(v, Builtin):
        return f"<builtin {v.name}>"
    return str(v)


def values_equal(a, b):
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return a == b


# ---------- environments ----------

class Env:
    def __init__(self, parent=None):
        self.vars = {}
        self.consts = set()
        self.parent = parent

    def lookup(self, name):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise LichenRuntimeError(f"Undefined variable '{name}'")

    def assign(self, name, value, const=False):
        if name in self.consts:
            raise LichenRuntimeError(f"Cannot reassign constant '{name}'")
        self.vars[name] = value
        if const:
            self.consts.add(name)


# ---------- builtins ----------

def _print(*args):
    print(" ".join(to_str(a) for a in args))
    return None


def _len(x):
    if isinstance(x, (str, list)):
        return len(x)
    raise LichenRuntimeError(f"len() needs a string or list, got {type_name(x)}")


def _str(x):
    return to_str(x)


def _int(x):
    if isinstance(x, bool):
        return 1 if x else 0
    if is_number(x):
        return int(x)
    if isinstance(x, str):
        try:
            return int(x.strip())
        except ValueError:
            raise LichenRuntimeError(f"Can't convert \"{x}\" to an int")
    raise LichenRuntimeError(f"Can't convert {type_name(x)} to an int")


def _float(x):
    if is_number(x):
        return float(x)
    if isinstance(x, str):
        try:
            return float(x.strip())
        except ValueError:
            raise LichenRuntimeError(f"Can't convert \"{x}\" to a float")
    raise LichenRuntimeError(f"Can't convert {type_name(x)} to a float")


def _range(*args):
    for a in args:
        if not isinstance(a, int) or isinstance(a, bool):
            raise LichenRuntimeError("range() only takes whole numbers")
    if len(args) == 3 and args[2] == 0:
        raise LichenRuntimeError("range() step can't be 0")
    return list(range(*args))


def _input(prompt=""):
    return input(to_str(prompt))


def _push(lst, item):
    if not isinstance(lst, list):
        raise LichenRuntimeError(f"push() needs a list, got {type_name(lst)}")
    lst.append(item)
    return None


BUILTINS = [
    Builtin("print", _print, 0, None),
    Builtin("len", _len, 1, 1),
    Builtin("str", _str, 1, 1),
    Builtin("int", _int, 1, 1),
    Builtin("float", _float, 1, 1),
    Builtin("range", _range, 1, 3),
    Builtin("input", _input, 0, 1),
    Builtin("push", _push, 2, 2),
]


# ---------- the interpreter ----------

class Interpreter:
    def __init__(self):
        sys.setrecursionlimit(6000)
        self.globals = Env()
        for b in BUILTINS:
            self.globals.vars[b.name] = b

    def run(self, program, echo=False):
        """Run a parsed program. With echo=True (the REPL), bare top-level
        expressions print their value."""
        try:
            for stmt in program.body:
                if echo and isinstance(stmt, ExprStmt):
                    value = self.eval(stmt.expr, self.globals)
                    if value is not None:
                        print(to_str(value, True))
                else:
                    self.exec(stmt, self.globals)
        except ReturnSignal as r:
            raise LichenRuntimeError("'return' outside of a function", r.line)
        except RecursionError:
            raise LichenRuntimeError("Stack overflow (too much recursion)")

    # ----- statements -----

    def exec_block(self, body, env):
        for stmt in body:
            self.exec(stmt, env)

    def exec(self, node, env):
        try:
            getattr(self, "exec_" + type(node).__name__)(node, env)
        except LichenRuntimeError as e:
            if e.line is None:
                e.line = getattr(node, "line", 0) or None
            raise

    def exec_ExprStmt(self, node, env):
        self.eval(node.expr, env)

    def exec_Assign(self, node, env):
        value = self.eval(node.value, env)
        env.assign(node.name, value, node.const)

    def exec_Return(self, node, env):
        value = self.eval(node.value, env) if node.value is not None else None
        raise ReturnSignal(value, node.line)

    def exec_If(self, node, env):
        for branch in node.branches:
            if self.eval(branch.cond, env):
                self.exec_block(branch.body, env)
                return
        if node.else_body is not None:
            self.exec_block(node.else_body, env)

    def exec_While(self, node, env):
        while self.eval(node.cond, env):
            try:
                self.exec_block(node.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_Break(self, node, env):
        raise BreakSignal()

    def exec_Continue(self, node, env):
        raise ContinueSignal()

    def exec_For(self, node, env):
        iterable = self.eval(node.iterable, env)
        if not isinstance(iterable, (list, str)):
            raise LichenRuntimeError(f"Can't loop over a {type_name(iterable)}")
        for item in list(iterable):
            env.assign(node.var, item)
            try:
                self.exec_block(node.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_FnDef(self, node, env):
        env.assign(node.name, Function(node.name, node.params, node.body, env))

    # ----- expressions -----

    def eval(self, node, env):
        try:
            return getattr(self, "eval_" + type(node).__name__)(node, env)
        except LichenRuntimeError as e:
            if e.line is None:
                e.line = getattr(node, "line", 0) or None
            raise

    def eval_Num(self, node, env):
        return node.value

    def eval_Str(self, node, env):
        return node.value

    def eval_Bool(self, node, env):
        return node.value

    def eval_Name(self, node, env):
        return env.lookup(node.name)

    def eval_ListLit(self, node, env):
        return [self.eval(item, env) for item in node.items]

    def eval_Unary(self, node, env):
        value = self.eval(node.operand, env)
        if node.op == "not":
            return not value
        if not is_number(value):
            raise LichenRuntimeError(f"Can't negate a {type_name(value)}")
        return -value

    def eval_Binary(self, node, env):
        op = node.op

        if op == "and":
            left = self.eval(node.left, env)
            return self.eval(node.right, env) if left else left
        if op == "or":
            left = self.eval(node.left, env)
            return left if left else self.eval(node.right, env)

        left = self.eval(node.left, env)
        right = self.eval(node.right, env)

        if op == "==":
            return values_equal(left, right)
        if op == "!=":
            return not values_equal(left, right)

        if op in ("in", "not in"):
            if isinstance(right, str):
                if not isinstance(left, str):
                    raise LichenRuntimeError("Can only look for a string inside a string")
                found = left in right
            elif isinstance(right, list):
                found = any(values_equal(left, item) for item in right)
            else:
                raise LichenRuntimeError(
                    f"Can't use '{op}' with a {type_name(right)} on the right")
            return found if op == "in" else not found

        if op == "+":
            if is_number(left) and is_number(right):
                return left + right
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            if isinstance(left, list) and isinstance(right, list):
                return left + right
            raise LichenRuntimeError(
                f"Can't add {type_name(left)} and {type_name(right)}"
                + (" (try str(...))" if isinstance(left, str) or isinstance(right, str) else "")
            )

        if op in ("<", ">", "<=", ">="):
            both_nums = is_number(left) and is_number(right)
            both_strs = isinstance(left, str) and isinstance(right, str)
            if not (both_nums or both_strs):
                raise LichenRuntimeError(f"Can't compare {type_name(left)} and {type_name(right)}")
            return {"<": left < right, ">": left > right,
                    "<=": left <= right, ">=": left >= right}[op]

        # - * / %
        if not (is_number(left) and is_number(right)):
            raise LichenRuntimeError(
                f"Can't use '{op}' on {type_name(left)} and {type_name(right)}")
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "%":
            if right == 0:
                raise LichenRuntimeError("Modulo by zero")
            return left % right
        if right == 0:
            raise LichenRuntimeError("Division by zero")
        if isinstance(left, int) and isinstance(right, int) and left % right == 0:
            return left // right
        return left / right

    def eval_Index(self, node, env):
        obj = self.eval(node.obj, env)
        index = self.eval(node.index, env)
        if not isinstance(obj, (list, str)):
            raise LichenRuntimeError(f"Can't index a {type_name(obj)}")
        if not isinstance(index, int) or isinstance(index, bool):
            raise LichenRuntimeError("Index must be a whole number")
        if not -len(obj) <= index < len(obj):
            raise LichenRuntimeError(f"Index {index} is out of range (length {len(obj)})")
        return obj[index]

    def eval_Call(self, node, env):
        fn = self.eval(node.func, env)
        args = [self.eval(a, env) for a in node.args]

        if isinstance(fn, Builtin):
            n = len(args)
            if n < fn.min_args or (fn.max_args is not None and n > fn.max_args):
                raise LichenRuntimeError(f"Wrong number of arguments for {fn.name}()")
            return fn.func(*args)

        if isinstance(fn, Function):
            if len(args) != len(fn.params):
                raise LichenRuntimeError(
                    f"{fn.name}() takes {len(fn.params)} argument(s) but got {len(args)}")
            local = Env(fn.closure)
            for param, arg in zip(fn.params, args):
                local.vars[param] = arg
            try:
                self.exec_block(fn.body, local)
            except ReturnSignal as r:
                return r.value
            return None

        raise LichenRuntimeError(f"Can't call a {type_name(fn)}")
