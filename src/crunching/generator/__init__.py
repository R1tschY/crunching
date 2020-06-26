# -*- coding=utf-8 -*-
from abc import ABC, abstractmethod
from itertools import count
from textwrap import dedent, indent
from typing import AbstractSet, Any, Container, Generic, Iterable, Optional, \
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
               f"{INDENTION}return result"


class PyCodeGenContext:
    def __init__(self, parent: Optional["PyCodeGenContext"],
                 function: PyCodeGenFunction, input_var="input",
                 start_var="start", end_var="end", return_var="result", indent=""):
        self.parent = parent
        self.input_var = input_var
        self.start_var = start_var
        self.end_var = end_var
        self.return_var = return_var
        self.indent = indent
        self.function = function

    def gen_pycode(self, tree: Parser[T]) -> str:
        return indent(dedent(tree.gen_pycode(self)), self.indent)

    def new_child(self, start_var: str, end_var: str, return_var: str) -> "PyCodeGenContext":
        return PyCodeGenContext(
            parent=self,  # TODO: weakref
            input_var=self.input_var,
            start_var=start_var,
            end_var=end_var,
            return_var=return_var,
            indent=self.indent,
            function=self.function
        )

    def new_local(self, *args, **kwargs) -> str:
        return self.function.new_local(*args, **kwargs)

    def fix_indention(self, code: str):
        return indent(dedent(code), self.indent)


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
        return f"""
            if {context.input_var}.startswith({self.tag!r}, {context.start_var}, {context.end_var}):
                {context.return_var} = {context.start_var} + {len(self.tag)}, {self.tag!r}
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
        for parser in self.parsers:
            result = context.new_local("result")
            results.append(result)
            inner_ctx = context.new_child(
                start, context.end_var, f"{start}, {result}")
            lines.append(parser.gen_pycode(inner_ctx))

        lines.append(context.fix_indention(
            f"{context.return_var} = {start}, ({', '.join(results)})"))
        return "\n".join(lines)


if __name__ == '__main__':
    print(PyCodeGenerator().generate(Tuple(Tag("#"), Tag("+"))))
