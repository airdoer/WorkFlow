# -*- coding: utf-8 -*-
# @program c1
# @author chenzhixu@kuaishou.com
# @date 2024/2/4 21:38
# @description:
#   something

from openpyxl import worksheet
from .CellType import parse_cell_type, Parser


class XlsxHeader(object):
    def __init__(self, column_idx, name, fullname, descriptor, header_type):
        self.column_idx = column_idx
        self.name = name
        self.fullname = fullname
        self.descriptor = descriptor
        self.header_parser: Parser = parse_cell_type(header_type)

    def parse_cell(self, data, value_cb):
        return self.header_parser.parse(data, value_cb)

    def get_header(self):
        # 返回给外部（比如web前端）的所有序列化信息
        return {
            'name': self.name,  # 字段
            'fullname': self.fullname,  # 列名
            'descriptor': self.descriptor,  # 备注
            'type': self.header_parser.flag,  # 类型
        }


def create_xlsx_table(meta_info, work_sheet: worksheet):
    headers = []
    datas = []
    header_names = []
    header_fullnames = []
    header_descriptors = []

    idx = 0
    for row in work_sheet.iter_rows(values_only=True):
        idx += 1
        if idx == 1:  # 备注 name
            if row[0] != "备注":  # 有些表不需要导出，用这个来作为标志位
                return None
            header_names = row[1:]
            while header_names[-1] is None:  # 有些表格会在右侧添加备注的字段，需要剔除
                header_names = header_names[:-1]
        elif idx == 2:  # 注释-列名 fullname
            header_fullnames = row[1:]
        elif idx == 3:  # 注释-备注 descriptor
            header_descriptors = row[1:]
        elif idx == 4:  # 注释-类型 header_type
            header_types = row[1:]
            for i in range(len(header_names)):
                if header_types[i] is None:  # 注释-类型为空的不需要导出
                    continue
                column_idx = i
                headers.append(XlsxHeader(column_idx, header_names[i], header_fullnames[i], header_descriptors[i], header_types[i]))
        elif idx == 5:  # 约束类型
            pass
        else:  # data部分
            datas.append(row[1:])
    return XlsxTable(meta_info, headers, datas)


class XlsxTable(object):
    def __init__(self, meta_info, headers, datas):
        self.meta_info = meta_info
        # meta_info字段:
        #     'svn_version'
        #     'file_name'
        #     'sheet_name'
        #     'unique_name'
        # }
        self.search_index = {}  # key->list(row_idx)

        self.headers: list[XlsxHeader] = headers
        self.raw_datas = datas  # 是按行的所有string类型的数据
        # 最理想的应该是解析各个XXXDef.cs中的primaryKeys，不过可以先按照经验解法
        # 一般的id都是第一个，如果第一个有相同的，那么就采用1-2（应该能处理绝大多数情况）
        self.parse_datas = []  # 已经按照header解析后的
        self.col_cnt = len(self.headers)
        self.row_cnt = len(datas)

        self.keys_datas = []

        for i in range(self.row_cnt):
            parse_data = []
            if self.headers and datas[i][self.headers[0].column_idx] is None:
                continue
            for cur_header in self.headers:
                cell_data = cur_header.parse_cell(datas[i][cur_header.column_idx], lambda _k: self.parse_value_callback(i, _k))
                parse_data.append(cell_data)

            self.parse_datas.append(parse_data)

    def get_headers(self):
        return [h.get_header() for h in self.headers]

    def parse_value_callback(self, row_index, _value):
        if _value not in [None, 0, False, True, 'None', 'False', 'True', '0', '0.0']:  # 涉及到默认值或bool值的，都过滤掉
            if _value not in self.search_index:
                self.search_index[_value] = []
            if row_index not in self.search_index[_value]:
                self.search_index[_value].append(row_index)

    def search_key(self, key: str):
        if key not in self.search_index:
            raise ValueError(f"search_key {key} not in xlsx({self.meta_info['unique_name']})'s search_index")
        else:
            return list(self.search_index[key])

    def search_keys(self, keys: list[str]):  # 针对多个搜索词
        valid_rows = set.intersection(*(set(self.search_index.get(k, [])) for k in keys))
        valid_rows = sorted(list(valid_rows))
        return valid_rows

    def getRowByIdx(self, row_id):  # 行数据可以根据行号来获取
        return self.parse_datas[row_id]

    def getRowById(self, _id):  # 行数据可以根据主键（一般是Id）来获取
        pass

    def getColumn(self, column_name):  # 列数据需要根据备注key来获取，比如Id、Name等，用于获取数据的全量有效范围
        pass
