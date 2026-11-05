from lichen.nodes import (
    Num, Str, Bool, Name, ListLit, Unary, Binary, Call, Index,
    Assign, ExprStmt, Return, Branch, If, While, For, FnDef, Program,
)


class ParseError(Exception):
    pass


def describe(tok):
    if tok.type == "EOF":
        return "end of file"
    if tok.type == "NEWLINE":
        return "end of line"
    if tok.type == "STRING":
        return f'"{tok.value}"'
    return f"'{tok.value}'"


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ---------- helpers ----------

    @property
    def tok(self):
        return self.tokens[self.pos]

    def peek(self, offset=1):
        return self.tokens[min(self.pos + offset, len(self.tokens) - 1)]

    def advance(self):
        t = self.tokens[self.pos]
        if t.type != "EOF":
            self.pos += 1
        return t

    def check(self, *types):
        return self.tok.type in types

    def match(self, *types):
        if self.check(*types):
            return self.advance()
        return None

    def error(self, msg):
        return ParseError(f"{msg} at line {self.tok.line}, col {self.tok.col}")

    def expect(self, type_, what=None):
        if self.check(type_):
            return self.advance()
        raise self.error(f"Expected {what or type_}, got {describe(self.tok)}")

    def skip_newlines(self):
        while self.check("NEWLINE"):
            self.advance()

    def end_statement(self):
        if self.check("NEWLINE"):
            self.advance()
        elif not self.check("}", "EOF"):
            raise self.error(f"Expected end of line, got {describe(self.tok)}")

    # ---------- statements ----------

    def parse_program(self):
        body = []
        self.skip_newlines()
        while not self.check("EOF"):
            body.append(self.statement())
            self.skip_newlines()
        return Program(body)

    def block(self):
        self.expect("{", "'{'")
        self.skip_newlines()
        body = []
        while not self.check("}"):
            if self.check("EOF"):
                raise self.error("Missing closing '}'")
            body.append(self.statement())
            self.skip_newlines()
        self.expect("}")
        return body

    def statement(self):
        t = self.tok
        if t.type == "const":
            return self.const_decl()
        if t.type == "fn":
            return self.fn_def()
        if t.type == "if":
            return self.if_stmt()
        if t.type == "while":
            self.advance()
            cond = self.expression()
            return While(cond, self.block())
        if t.type == "for":
            return self.for_stmt()
        if t.type == "return":
            return self.return_stmt()
        if t.type == "NAME" and self.peek().type in ("=", "+=", "-=", "++", "--"):
            return self.assignment()
        expr = self.expression()
        self.end_statement()
        return ExprStmt(expr)

    def const_decl(self):
        kw = self.advance()
        name = self.expect("NAME", "a name after 'const'")
        self.expect("=", "'=' after the constant's name")
        value = self.expression()
        self.end_statement()
        return Assign(name.value, value, True, kw.line)

    def assignment(self):
        name = self.advance()
        op = self.advance()
        if op.type == "=":
            value = self.expression()
        elif op.type in ("+=", "-="):
            rhs = self.expression()
            value = Binary(op.type[0], Name(name.value, name.line), rhs, name.line)
        else:  # ++ or --
            value = Binary(op.type[0], Name(name.value, name.line), Num(1), name.line)
        self.end_statement()
        return Assign(name.value, value, False, name.line)

    def fn_def(self):
        kw = self.advance()
        name = self.expect("NAME", "a function name")
        self.expect("(", "'('")
        params = []
        if not self.check(")"):
            params.append(self.expect("NAME", "a parameter name").value)
            while self.match(","):
                params.append(self.expect("NAME", "a parameter name").value)
        self.expect(")", "')'")
        return FnDef(name.value, params, self.block(), kw.line)

    def if_stmt(self):
        self.advance()
        cond = self.expression()
        branches = [Branch(cond, self.block())]
        else_body = None
        while True:
            save = self.pos
            self.skip_newlines()
            if self.check("elif"):
                self.advance()
                cond = self.expression()
                branches.append(Branch(cond, self.block()))
            elif self.check("else"):
                self.advance()
                else_body = self.block()
                break
            else:
                self.pos = save
                break
        return If(branches, else_body)

    def for_stmt(self):
        kw = self.advance()
        var = self.expect("NAME", "a loop variable name")
        self.expect("in", "'in'")
        iterable = self.expression()
        return For(var.value, iterable, self.block(), kw.line)

    def return_stmt(self):
        kw = self.advance()
        value = None
        if not self.check("NEWLINE", "}", "EOF"):
            value = self.expression()
        self.end_statement()
        return Return(value, kw.line)

    # ---------- expressions (lowest precedence first) ----------

    def expression(self):
        return self.or_expr()

    def or_expr(self):
        left = self.and_expr()
        while self.check("or"):
            t = self.advance()
            left = Binary("or", left, self.and_expr(), t.line)
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.check("and"):
            t = self.advance()
            left = Binary("and", left, self.not_expr(), t.line)
        return left

    def not_expr(self):
        if self.check("not"):
            t = self.advance()
            return Unary("not", self.not_expr(), t.line)
        return self.comparison()

    def comparison(self):
        left = self.additive()
        while self.check("==", "!=", "<", ">", "<=", ">="):
            t = self.advance()
            left = Binary(t.type, left, self.additive(), t.line)
        return left

    def additive(self):
        left = self.term()
        while self.check("+", "-"):
            t = self.advance()
            left = Binary(t.type, left, self.term(), t.line)
        return left

    def term(self):
        left = self.unary()
        while self.check("*", "/"):
            t = self.advance()
            left = Binary(t.type, left, self.unary(), t.line)
        return left

    def unary(self):
        if self.check("-"):
            t = self.advance()
            return Unary("-", self.unary(), t.line)
        return self.postfix()

    def postfix(self):
        expr = self.primary()
        while True:
            if self.check("("):
                t = self.advance()
                args = self.comma_list(")")
                expr = Call(expr, args, t.line)
            elif self.check("["):
                t = self.advance()
                self.skip_newlines()
                index = self.expression()
                self.skip_newlines()
                self.expect("]", "']'")
                expr = Index(expr, index, t.line)
            else:
                break
        return expr

    def comma_list(self, close):
        items = []
        self.skip_newlines()
        while not self.check(close):
            items.append(self.expression())
            self.skip_newlines()
            if not self.match(","):
                break
            self.skip_newlines()
        self.expect(close, f"'{close}'")
        return items

    def primary(self):
        t = self.tok
        if t.type == "NUMBER":
            self.advance()
            return Num(t.value)
        if t.type == "STRING":
            self.advance()
            return Str(t.value)
        if t.type in ("true", "false"):
            self.advance()
            return Bool(t.type == "true")
        if t.type == "NAME":
            self.advance()
            return Name(t.value, t.line)
        if t.type == "(":
            self.advance()
            expr = self.expression()
            self.expect(")", "')'")
            return expr
        if t.type == "[":
            self.advance()
            return ListLit(self.comma_list("]"))
        raise self.error(f"Expected an expression, got {describe(t)}")


def parse(tokens):
    return Parser(tokens).parse_program()
