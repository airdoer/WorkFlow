# -*- coding: utf-8 -*-
# @program c1
# @author chenzhixu@kuaishou.com
# @date 2024/2/5 16:37
# @description:
#   something


def parse_list_delimiter(sub_string):
    if sub_string == "":
        return "", ','
    last_char = sub_string[-1]
    if last_char == ')':  # 说明内部直接是子类型，没有delimiter
        return sub_string, ','
    if last_char not in ["'", '"']:  # 有一些内部类型直接是子类型，并且没有带()，做一下特判处理
        return sub_string, ','
    # 有一些是List(Int(), delimiter=",")，还有一些是List(Int(), ",")这种，所以要先找到前面的分隔逗号
    quote_idx = sub_string.rfind(last_char, 0, -1)  # 找到第一个引号的位置
    delimiter_str = sub_string[quote_idx + 1: -1]
    comma_idx = sub_string.rfind(',', 0, quote_idx)
    return sub_string[:comma_idx], delimiter_str


def parse_cell_type(cell_type):
    if cell_type is None:
        return NoneParser()
    if cell_type in [11, 12, 13, 14]:
        return NoneParser()
    cell_type.replace(" ", "")  # 去除所有的空格
    cell_type = cell_type.lower()
    if cell_type == "":
        return NoneParser()
    elif cell_type == "#":
        return NoneParser()
    elif cell_type.startswith("//"):  # 注释类型
        return NoneParser()
    elif cell_type in ["int()", "int"]:
        return IntParser()
    elif cell_type in ["float()", "float"]:
        return FloatParser()
    elif cell_type in ["str()", "str", "string()", "string"]:
        return StrParser()
    elif cell_type in ["desc()", "desc"]:
        return DescParser()
    elif cell_type in ["func()", "func"]:
        return FuncParser()
    elif cell_type in ["fp()", 'fp']:
        return FpParser()
    elif cell_type in ["bool()", "boolean()", "bool", "boolean"]:
        return BoolParser()
    elif cell_type in ["enum()", "enum"]:  # enum类型因为缺少具体的枚举信息，退化为string类型
        return EnumParser()
    elif cell_type in ["datetime", "datetime()"]:
        return DatetimeParser()
    elif cell_type.startswith("list(") and cell_type.endswith(")"):
        sub_string = cell_type[5:-1]
        sub_type_string, delimiter = parse_list_delimiter(sub_string)
        sub_parser = parse_cell_type(sub_type_string)
        return ListParser(sub_parser, delimiter=delimiter)
    elif cell_type in ['locktargetareadatalist']:  # 一些CustomType，用于额外的处理
        return CustomTypeParser()
    else:
        raise ValueError(f"Unknown type string {cell_type}")


class Parser:
    flag = ''

    def parse(self, value, value_cb):
        raise NotImplementedError("Subclasses must implement parse method")


class NoneParser(Parser):
    defaultValue = ''
    flag = 'None'

    def parse(self, value, value_cb):
        if value is None:
            return self.defaultValue
        value_cb(str(value))
        return str(value)


class IntParser(Parser):
    defaultValue = 0
    flag = 'Int'

    def parse(self, value, value_cb):
        if value is None:
            return self.defaultValue
        if value == '':
            return self.defaultValue
        try:
            value_cb(str(value))
            return int(value)
        except ValueError:
            raise ValueError(f"Invalid integer value {value}")


class FloatParser(Parser):
    defaultValue = 0.0
    flag = 'Float'

    def parse(self, value, value_cb):
        if value is None:
            return self.defaultValue
        if value == '':
            return self.defaultValue
        value_cb(str(value))
        if type(value) is str:
            return float(value)
        elif type(value) is float:
            return float(value)
        elif type(value) is int:
            return float(value)
        else:
            raise ValueError(f"Invalid float value {value}")


class StrParser(Parser):
    defaultValue = ''
    flag = 'Str'

    def parse(self, value, value_cb):
        if value is None:
            return self.defaultValue
        value_cb(str(value))
        return str(value)


class DescParser(Parser):
    # 备注类型
    defaultValue = ''
    flag = 'Desc'

    def parse(self, value, value_cb):
        if value is None:
            return self.defaultValue
        value_cb(str(value))
        return str(value)


class FuncParser(Parser):
    # Func解析目前和StrParser一样
    defaultValue = ''
    flag = 'Func'

    def parse(self, value, value_cb):
        if value is None:
            return self.defaultValue
        value_cb(str(value))
        return str(value)


class FpParser(Parser):
    # Fp中可能为int也可能为float，就是一种混合状态，比如1,0.1都有
    defaultValue = "0"
    flag = 'Fp'

    def parse(self, value, value_cb):
        if value is None:
            return self.defaultValue
        if value == '':
            return self.defaultValue
        value_cb(str(value))
        return value


class BoolParser(Parser):
    defaultValue = False
    flag = 'Bool'

    def parse(self, value, value_cb):
        if value is None:
            return self.defaultValue
        # bool值类型的不加入搜索索引
        # value_cb(str(value))
        if value == '':
            return False
        if type(value) is str:
            if value == '1' or value.lower() == 'true':
                return True
            return False
        if type(value) is int:
            return True
        if type(value) is bool:
            return value
        raise ValueError(f"Unknown bool value {value}")


class CustomTypeParser(Parser):
    defaultValue = ''
    flag = 'CustomType'

    def parse(self, value, value_cb):
        if value is None:
            return self.defaultValue
        value_cb(str(value))
        return str(value)


class EnumParser(Parser):
    defaultValue = ''
    flag = 'Enum'

    def parse(self, value, value_cb):
        if value is None:
            return self.defaultValue
        value_cb(str(value))
        return str(value)


class DatetimeParser(Parser):
    defaultValue = ''
    flag = 'Datetime'

    def parse(self, value, value_cb):
        if value is None:
            return self.defaultValue
        value_cb(str(value))
        return str(value)


class ListParser(Parser):
    defaultValue = []
    flag = 'List'

    def __init__(self, sub_parser, delimiter=","):
        self.sub_parser = sub_parser
        self.delimiter = delimiter
        self.flag = f'List({self.sub_parser.flag},"{self.delimiter}")'

    def parse(self, value, value_cb):
        if value is None:
            return self.defaultValue
        if value == '':
            return self.defaultValue
        # 对于ListParser，不用调用value_cb，而是用其内部的基本元素的Parser来调用
        if not isinstance(value, str):
            # 可能是单个元素的值，比如int或者double
            # raise ValueError("Invalid list value")
            return [self.sub_parser.parse(value, value_cb)]
        if self.delimiter not in value:
            # 可能是单个元素的值，比如str
            return [self.sub_parser.parse(value.strip(), value_cb)]

        items = value.split(self.delimiter)
        parsed_list = []
        for item in items:
            parsed_list.append(self.sub_parser.parse(item.strip(), value_cb))
        return parsed_list


def unitTest():
    assert parse_cell_type("List()").flag == 'List(None,",")'
    assert parse_cell_type("List(Int())").flag == 'List(Int,",")'
    assert parse_cell_type("List(FP(), delimiter=';')").flag == 'List(Fp,";")'
    assert parse_cell_type('List(Int(), delimiter=",")').flag == 'List(Int,",")'
    assert parse_cell_type('List(List(Str(), delimiter=";"))').flag == 'List(List(Str,";"),",")'
    assert parse_cell_type("List(FP(), ';')").flag == 'List(Fp,";")'
    assert parse_cell_type("List(Str(), '/')").flag == 'List(Str,"/")'
    assert parse_cell_type("List(Fp)").flag == 'List(Fp,",")'
    assert parse_cell_type("List(List(Str(), delimiter=';'), delimiter='/')").flag == 'List(List(Str,";"),"/")'


if __name__ == "__main__":
    unitTest()
