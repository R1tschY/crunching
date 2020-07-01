

from copy import copy
from typing import Callable, Generic, List, TypeVar, Union, Optional, \
    Tuple as TupleType

T = TypeVar("T")
U = TypeVar("U")

MutableInt = List[int]

NOT_MATCHING = (-1, None)

DEBUGING = False


class LoggingProxy:
    def __init__(self, parser, parser_fn):
        self.parser = parser
        self.parser_fn = parser_fn

    def __call__(self, input: str, start: MutableInt, end: int):
        print(f"START {self.parser} start={start} end={end}")
        result = self.parser_fn(input, start, end)
        if start[0] >= 0:
            print(f"SUCCESS {self.parser} start={start[0]} result={result}")
        else:
            print(f"FAILED {self.parser}")
        return result


class Parser(Generic[T]):
    def as_parser(self) -> Callable[
            [str, MutableInt, int], Optional[T]]:
        parser = self._as_parser()
        if DEBUGING:
            return LoggingProxy(self, parser)
        else:
            return parser

    def _as_parser(self) -> Callable[
            [str, MutableInt, int], Optional[T]]:
        raise NotImplementedError()


class Alt(Parser[T]):
    def __init__(self, *parsers):
        self.parsers = [into_parser(p) for p in parsers]

    def _as_parser(self):
        parsers = [p.as_parser() for p in self.parsers]

        def parse(ipt: str, start: MutableInt, end: int):
            for parser in parsers:
                old_start = start[0]
                result = parser(ipt, start, end)
                if start[0] >= 0:
                    #assert start > old_start
                    return result
                else:
                    start[0] = old_start
            return NOT_MATCHING

        return parse


class Tag(Parser[T]):
    def __init__(self, tag: str):
        self.tag = tag

    def _as_parser(self):
        tag = self.tag
        assert len(tag) > 0
        tag_len = len(tag)
        _NOT_MATCHING = NOT_MATCHING

        # def parse(ipt: str, start: int, end: int):
        #     if ipt.startswith(tag, start, end):
        #         return start + len(tag), tag
        #     else:
        #         return NOT_MATCHING
        if tag_len != 1:
            def parse(ipt: str, start: int, end: int):
                if ipt[start:start + tag_len] == tag:
                    return start + tag_len, tag
                else:
                    return _NOT_MATCHING
        else:
            tag = tag[0]  # for bytes convert to int
            def parse(ipt: str, start: int, end: int):
                if ipt[start] == tag:
                    return start + 1, tag
                else:
                    return _NOT_MATCHING
        return parse


class CharExcluding(Parser[T]):
    def __init__(self, chars: Union[str, List[str]]):
        self.chars = list(chars)

    def _as_parser(self):
        def parser(input: str, start: int, end: int) -> TupleType[int, str]:
            c = input[start]
            if c not in self.chars:
                return start + 1, c
            else:
                return NOT_MATCHING
        return parser

    def as_predicate(self):
        chars = self.chars
        return lambda x: x not in chars

    def including(self, chars: str):
        new_chars = copy(self.chars)
        for char in chars:
            if char not in new_chars:
                new_chars.append(char)
        return Charset(new_chars)

    def excluding(self, chars: str):
        new_chars = copy(self.chars)
        for char in chars:
            new_chars.remove(char)
        return Charset(new_chars)


class AnyChar(Parser[T]):
    def _as_parser(self):
        def parser(input, start, end):
            return start + 1, input[start]
        return parser

    def as_predicate(self):
        return True


class Charset(Parser[T]):
    def __init__(self, chars: Union[str, List[str]]):
        self.chars = list(chars)

    def _as_parser(self):
        def parser(input, start, end):
            c = input[start]
            if c in self.chars:
                return start + 1, c
            else:
                return NOT_MATCHING
        return parser

    def as_predicate(self):
        return self.chars.__contains__

    def including(self, chars: str):
        new_chars = copy(self.chars)
        for char in chars:
            if char not in new_chars:
                new_chars.append(char)
        return Charset(new_chars)

    def excluding(self, chars: str):
        new_chars = copy(self.chars)
        for char in chars:
            new_chars.remove(char)
        return Charset(new_chars)


class Tuple(Parser[T]):
    def __init__(self, *parsers):
        self.parsers = [into_parser(p) for p in parsers]

    def _as_parser(self):
        parsers = [p.as_parser() for p in self.parsers]
        parsers_len = len(parsers)
        parsers_enum = list(enumerate(parsers))
        results_proto = parsers_len * [None]
        _NOT_MATCHING = NOT_MATCHING

        def parse(ipt: str, start: int, end: int):
            results = results_proto[:]
            for i, parser in parsers_enum:
                old_start = start
                start, results[i] = parser(ipt, start, end)
                if start < 0:
                    return _NOT_MATCHING
                assert start > old_start

                if start == end and i != parsers_len - 1:
                    return _NOT_MATCHING
            return start, results

        return parse


class MapRes(Generic[T, U], Parser[U]):
    def __init__(self, parser, mapper: Callable[[T], U]):
        self.parser = into_parser(parser)
        self.mapper = mapper

    def _as_parser(self):
        parser = self.parser.as_parser()
        mapper = self.mapper
        _NOT_MATCHING = NOT_MATCHING

        def parse(ipt: str, start: int, end: int):
            start, result = parser(ipt, start, end)
            if start < 0:
                return _NOT_MATCHING
            else:
                return start, mapper(result)

        return parse


class TakeWhile(Parser[T]):
    def __init__(self, predicate, n, m):
        self.predicate = predicate
        self.n = n
        self.m = m

    def _as_parser(self):
        predicate = self.predicate.as_predicate()
        n = self.n
        m = self.m

        if n is None and m is None:
            def parse(ipt: str, start: int, end: int):
                i = start
                for i in range(start, end):
                    if not predicate(ipt[i]):
                        return i - 1, ipt[start:i]
                return i - 1, ipt[start:i]
        elif n is not None and m is not None:
            def parse(ipt: str, start: int, end: int):
                i = start
                for i in range(start, min(start + m, end)):
                    if not predicate(ipt[i]):  # TODO: take_until?
                        if i < start + n:
                            return NOT_MATCHING
                        else:
                            break
                else:
                    i += 1

                return i, ipt[start:i]
        else:
            raise NotImplementedError()

        return parse


class Many(Parser[T]):
    def __init__(self, parser: Parser[T], n: int = None, m: int = None):
        self.parser = into_parser(parser)
        self.n = n
        self.m = m

    def _as_parser(self):
        parser = self.parser.as_parser()
        n = self.n
        m = self.m

        if n is None and m is None:
            def parse(ipt: str, start: int, end: int):
                results = []
                while start != end:
                    old_start = start
                    start, result = parser(ipt, start, end)
                    if start < 0:
                        start = old_start
                        break

                    assert start > old_start
                    results.append(result)

                return start, results

        elif n is not None and m is not None:
            def parse(ipt: str, start: int, end: int):
                results = []
                i = 0
                for i in range(m):
                    old_start = start
                    start, result = parser(ipt, start, end)
                    if start < 0 or start == end:
                        break
                    assert start > old_start

                    results.append(result)

                if i < n:
                    return NOT_MATCHING
                return start, results
        else:
            raise NotImplementedError()

        return parse


def into_parser(parser: Union[Parser[T], str]) -> Union[Parser[T], Parser[str]]:
    if isinstance(parser, (str, bytes)):
        return Tag(parser)

    return parser


def parse(parser: Parser[T], ipt: str) -> TupleType[str, Optional[T]]:
    len_input = len(ipt)
    start, result = into_parser(parser).as_parser()(ipt, 0, len_input)
    return ipt[start:len_input], result




