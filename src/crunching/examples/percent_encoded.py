# -*- coding=utf-8 -*-
import string
from urllib.parse import unquote

from crunching import Alt, AnyChar, CharExcluding, Charset, Many, MapRes, Tag, \
    Tuple, \
    into_parser, parse

hexdigit = Charset(string.hexdigits.encode("ascii"))

hex2chr = {
    (x + y).encode("ascii"): bytes.fromhex(x + y)[0]
    for x in string.hexdigits
    for y in string.hexdigits
}

hexnipple = {
    x: i
    for i, x in enumerate(string.hexdigits.encode("ascii"))
}

percent_enc = MapRes(
    Many(Alt(
        MapRes(Tuple(b"%", hexdigit, hexdigit), lambda res: hexnipple[res[2]] | (hexnipple[res[1]] << 0)),
        AnyChar())),
    lambda res: bytes(res)
)


def test_hexdigit():
    assert parse(hexdigit, b"1") == (b"", b"1")
    assert parse(hexdigit, b"F") == (b"", b"F")
    assert parse(hexdigit, b"f") == (b"", b"f")
    assert parse(hexdigit, b"f12") == (b"12", b"f")


def test_percent_enc():
    assert parse(percent_enc, b"1") == (b"", b"1")
    assert parse(percent_enc, b"%20") == (b"", b"\x20")


def test_percent_enc_pref(benchmark):
    testdata = b"https://www.google.com/search?channel=fs&" \
               b"q=%C3%84+wie+%C3%96+%C2%A7%24%25&ie=utf-8&oe=utf-8"
    @benchmark
    def parse_me():
        parse(percent_enc, testdata)


def test_percent_enc_pref2(benchmark):
    testdata = b"https://www.google.com/search?channel=fs&" \
               b"q=%C3%84+wie+%C3%96+%C2%A7%24%25&ie=utf-8&oe=utf-8"
    parser = into_parser(percent_enc).as_parser()

    @benchmark
    def parse_me():
        len_input = len(testdata)
        start, result = parser(testdata, 0, len_input)
        return result


def test_percent_enc_pref_unquote(benchmark):
    testdata = "https://www.google.com/search?channel=fs&" \
               "q=%C3%84+wie+%C3%96+%C2%A7%24%25&ie=utf-8&oe=utf-8"

    @benchmark
    def parse_me():
        return unquote(testdata)
