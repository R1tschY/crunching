# -*- coding=utf-8 -*-
from crunching import Charset

seperators = Charset("()<>@,;:\\\"/[]?={} \t")
ctl = Charset("".join([chr(i) for i in range(32)]) + "\x127")

token = TakeWhileNot(seperators.including(ctl), 1, None)

parser = TupleSpaceSeperated("Content-Disposition", ":", disposition_type,
               MapRes(ManySpaceSeperated(Preceding(";", disp_ext_param)), dict))
disp_ext_type = token
disposition_type = Alt(Tag("inline"), Tag("attachment"), disp_ext_type)

filename_parm = Alt(Tuple(Tag("filename"), Tag("="), value),
                    Tuple(Tag("filename*"), Tag("="), ext_value))
disposition_parm = Alt(filename_parm, disp_ext_param)

disp_ext_parm = MapRes(
    Alt(Tuple(token, Tag("="), value),
        Tuple(ext_token, Tag("="), ext_value),
    lambda res: (res[0], res[2])
)
ext_token = MapRes(Tuple(token, Tag("*")), lambda res: res[0])
quoted_string = Delimited(Tag("\""), Many(Alt(qdtext, quoted_pair)), Tag("\""))
text = CharsetExcept(ctl.except_("\r\n \t"))
char = Charset(lambda x: x.isascii())
qdtext = text.except_("\"")
quoted_pair = Tuple(Tag("\\"), char)
value = Alt(token, quoted_pair)

mime_charset = TakeWhile(alpha.including(digit).including("!#$%&+-^_`{}~"), 1, None)
charset = Alt(Tag("UTF-8"), Tag("ISO-8859-1"), mime_charset)
ext_value = Tuple(charset, Tag("'"), Opt(language), Tag("'"), value_chars)

attr_char = Charset(alpha.including(digit).including("!#$&+-.^_`|~"))  # token except ( "*" / "'" / "%" )
value_chars = MapRes(
    Many(Alt(
        MapRes(Tuple(Tag("%"), hexdigit, hexdigit), lambda res: chr(int(res[1] + res[2], 16))),
        attr_char)),
    "".join
)
