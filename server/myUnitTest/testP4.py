import unittest
from utility.p4Utils import parse_p4_path, normalize_p4_path, get_filename, get_table_data_name



class TestP4Case(unittest.TestCase):
    def setUp(self):
        pass
    
    def test_path_analyze(self):
        # 测试标准路径格式
        p1 = "//C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData.lua#2"
        # 测试版本号在文件名中的格式
        p2 = "//C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData#2.lua"
        # 测试无版本号的路径
        p3 = "//C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData.lua"

        # 测试parse_p4_path函数
        parsed_p1 = parse_p4_path(p1)
        self.assertEqual(parsed_p1['dir'], "//C7/Development/Mainline/Server/script_lua/Data/Excel/")
        self.assertEqual(parsed_p1['name'], "FStatePropData")
        self.assertEqual(parsed_p1['ext'], ".lua")
        self.assertEqual(parsed_p1['rev'], "2")

        parsed_p2 = parse_p4_path(p2)
        self.assertEqual(parsed_p2['dir'], "//C7/Development/Mainline/Server/script_lua/Data/Excel/")
        self.assertEqual(parsed_p2['name'], "FStatePropData")
        self.assertEqual(parsed_p2['ext'], ".lua")
        self.assertEqual(parsed_p2['rev'], "2")

        parsed_p3 = parse_p4_path(p3)
        self.assertEqual(parsed_p3['dir'], "//C7/Development/Mainline/Server/script_lua/Data/Excel/")
        self.assertEqual(parsed_p3['name'], "FStatePropData")
        self.assertEqual(parsed_p3['ext'], ".lua")
        self.assertEqual(parsed_p3['rev'], None)

        # 测试normalize_p4_path函数
        self.assertEqual(normalize_p4_path(p1), "//C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData.lua#2")
        self.assertEqual(normalize_p4_path(p2), "//C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData.lua#2")
        self.assertEqual(normalize_p4_path(p3), "//C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData.lua")

        # 测试get_filename函数
        self.assertEqual(get_filename(p1), "FStatePropData.lua")
        self.assertEqual(get_filename(p2), "FStatePropData.lua")
        self.assertEqual(get_filename(p3), "FStatePropData.lua")

    def test_special_cases(self):
        # 测试无扩展名的文件
        no_ext_path = "//C7/Development/Mainline/Server/script_lua/Data/Excel/ReadMe#3"
        parsed = parse_p4_path(no_ext_path)
        self.assertEqual(parsed['name'], "ReadMe")
        self.assertEqual(parsed['ext'], "")
        self.assertEqual(parsed['rev'], "3")
        self.assertEqual(normalize_p4_path(no_ext_path), "//C7/Development/Mainline/Server/script_lua/Data/Excel/ReadMe#3")
        self.assertEqual(get_filename(no_ext_path), "ReadMe")

    def test_table_name(self):
        p4_path = "//C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData.lua#2"
        table_name = get_table_data_name(p4_path)
        self.assertEqual(table_name, "FStatePropData")

def doTest():
    # 不能直接调用unittest.main，docker会退出
    # unittest.main()
    test_p4_case = TestP4Case()
    test_p4_case.setUp()
    test_p4_case.test_path_analyze()
    test_p4_case.test_special_cases()
    test_p4_case.test_table_name()

# from myUnitTest import testP4
# testP4.doTest()

if __name__ == '__main__':
    doTest()
