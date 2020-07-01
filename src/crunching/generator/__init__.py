# -*- coding=utf-8 -*-
from abc import ABC, abstractmethod
from itertools import count
from textwrap import dedent, indent
from typing import AbstractSet, Any, Callable, Container, Generic, Iterable, \
    Optional, \
    Set, \
    TypeVar

T = TypeVar("T")

INDENTION = "  " * 2


class Parser(Generic[T], ABC):
    @abstractmethod
    def parse(self, input: str, start: int, end: int):
        raise NotImplementedError()

    def _gen_pycode(self, context: "PyCodeGenContext") -> str:
        raise NotImplementedError()

    def gen_pycode(self, context: "PyCodeGenContext") -> str:
        return context.fix_indention(self._gen_pycode(context))


Predicate = Callable[[str], bool]


class NotMatchingError(Exception):
    def __init__(self, input: str, pos: int):
        super().__init__(input, pos)


def _new_name(prefix: str, names: Container[str]):
    for i in count():
        var = f"{prefix}_{i}"
        if var not in names:
            return var


class PyCodeGenGlobalContext:
    def __init__(self, main = "main"):
        self.main = PyCodeGenFunction(self, "main")
        self.functions = {"main": self.main}

    def new_function(self, prefix = "fn") -> "PyCodeGenFunction":
        new_name = _new_name(prefix, self.functions)
        fn = PyCodeGenFunction(self, new_name)  # TODO: weakref
        self.functions[new_name] = fn
        return fn

    def main_function(self) -> "PyCodeGenFunction":
        return self.main


class PyCodeGenFunction:
    def __init__(self, gctx: PyCodeGenGlobalContext, name: str):
        self.name = name
        self.locals = set()
        self.gctx = gctx
        self.ctx = PyCodeGenContext(None, self, indent=INDENTION)  # TODO: weakref

    def new_local(self, prefix: str = "var") -> str:
        new_name = _new_name(prefix, self.locals)
        self.locals.add(new_name)
        return new_name

    def gen_pycode(self, body: str) -> str:
        return f"def {self.name}(input: str, start: int, end: int):\n" \
               f"{body}\n" \
               f"{INDENTION}return new_start, result"


class PyCodeGenContext:
    def __init__(self, parent: Optional["PyCodeGenContext"],
                 function: PyCodeGenFunction, input_var="input",
                 start_var="start", end_var="end", result_var="result",
                 new_start_var="new_start", indent=""):
        self.parent = parent
        self.input_var = input_var
        self.start_var = start_var
        self.end_var = end_var
        self.result_var = result_var
        self.new_start_var = new_start_var
        self.indent = indent
        self.function = function

    def gen_pycode(self, tree: Parser[T]) -> str:
        return indent(dedent(tree.gen_pycode(self)), self.indent)

    def new_child(self, start_var: str, end_var: str, result_var: str,
                  new_start_var: str, indent: bool = False
                  ) -> "PyCodeGenContext":
        return PyCodeGenContext(
            parent=self,  # TODO: weakref
            input_var=self.input_var,
            start_var=start_var,
            end_var=end_var,
            result_var=result_var,
            new_start_var=new_start_var,
            indent=self.more_indent() if indent else self.indent,
            function=self.function
        )

    def new_local(self, *args, **kwargs) -> str:
        return self.function.new_local(*args, **kwargs)

    def fix_indention(self, code: str):
        return indent(dedent(code), self.indent)

    def more_indent(self) -> str:
        return self.indent + INDENTION


class PyCodeGenerator:

    def generate(self, tree: Parser[T]) -> str:
        gctx = PyCodeGenGlobalContext()
        context = gctx.main.ctx
        body = tree.gen_pycode(context)
        return gctx.main.gen_pycode(body)


class Tag(Parser[str]):
    def __init__(self, tag: str):
        self.tag = tag

    def parse(self, input: str, start: int, end: int):
        if input.startswith(self.tag, start, end):
            return start + len(self.tag), self.tag
        else:
            raise NotMatchingError(input, start)

    def _gen_pycode(self, context: PyCodeGenContext) -> str:
        if len(self.tag) == 1:
            return f"""
                if {context.input_var}[{context.start_var}] == {self.tag!r}:
                    {context.new_start_var} = {context.start_var} + {len(self.tag)}
                    {context.result_var} = {self.tag!r}
                else:
                    raise NotMatchingError({context.input_var}, {context.start_var})
            """

        return f"""
            if {context.input_var}.startswith({self.tag!r}, {context.start_var}, {context.end_var}):
                {context.new_start_var} = {context.start_var} + {len(self.tag)}
                {context.result_var} = {self.tag!r}
            else:
                raise NotMatchingError({context.input_var}, {context.start_var})
        """


class Tuple(Parser[Iterable[Any]]):
    def __init__(self, *parsers: Parser[Any]):
        self.parsers = parsers

    def parse(self, input: str, start: int, end: int):
        results = []
        for parser in self.parsers:
            start, result = parser.parse(input, start, end)
            results.append(result)
        return results

    def gen_pycode(self, context: PyCodeGenContext) -> str:
        lines = []
        start = context.new_local("start")
        results = []

        lines.append(context.fix_indention(f"{start} = {context.start_var}"))
        for parser in self.parsers:
            result = context.new_local("result")
            results.append(result)
            inner_ctx = context.new_child(start, context.end_var, result, start)
            lines.append(parser.gen_pycode(inner_ctx))

        lines.append(context.fix_indention(
            f"{context.result_var} = ({', '.join(results)})"))
        lines.append(context.fix_indention(
            f"{context.new_start_var} = {start}"))
        return "\n".join(lines)


class Alt(Parser[T]):
    def __init__(self, *parsers: Parser[T]):
        self.parsers = parsers

    def parse(self, input: str, start: int, end: int):
        for parser in self.parsers:
            try:
                start, result = parser.parse(input, start, end)
            except NotMatchingError:
                continue
            else:
                return result
        raise NotMatchingError(input, start)

    def gen_pycode(self, context: PyCodeGenContext) -> str:
        lines = []
        not_found = context.new_local("not_found")
        result = context.new_local("result")

        lines.append(context.fix_indention(f"{not_found} = True"))
        for parser in self.parsers:
            lines.append(context.fix_indention(f"if {not_found}:"))
            if_ctx = context.new_child(
                context.start_var, context.end_var, result, context.new_start_var,
                indent=True)

            inner_ctx = if_ctx.new_child(
                context.start_var, context.end_var, result, context.new_start_var,
                indent=True)
            lines.append(if_ctx.fix_indention("try:"))
            lines.append(parser.gen_pycode(inner_ctx))
            lines.append(inner_ctx.fix_indention(f"{not_found} = False"))
            lines.append(if_ctx.fix_indention("except NotMatchingError:"))
            lines.append(inner_ctx.fix_indention("continue"))

        lines.append(context.fix_indention(f"if {not_found}:"))
        if_ctx = context.new_child(
            context.start_var, context.end_var, "", context.new_start_var,
            indent=True)
        lines.append(if_ctx.fix_indention(
            f"raise NotMatchingError({context.input_var}, {context.start_var})"))

        lines.append(context.fix_indention(
            f"{context.result_var} = {result}"))
        return "\n".join(lines)

    def as_regex(self) -> Optional[str]:
        return "|".join([
            parser.as_regex()
            for parser in self.parsers
        ])


class Charset(Predicate):
    def __init__(self, chars: str):
        self.chars = chars
        self.__call__ = self.chars.__contains__

    def _gen_pycode(self, context: "PyCodeGenContext") -> str:
        pass


if __name__ == '__main__':
    print(PyCodeGenerator().generate(Alt(Tag("#"), Tag("+"))))
