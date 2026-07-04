import unittest
from Implement.hotfixImpl.luaImp import LuaEnv, LuaLangStringWrapper


class TestLuaCase(unittest.TestCase):
    def setUp(self):
        self.lua_env = LuaEnv()
        self.lua_env.prepare_env()
    
    def test_climate_data(self):
        luaFilePath = "/app/p4WorkSpace/C7/Development/Mainline/Server/script_lua/tmp/Data/Excel/ClimateConstData.lua"
        with open(luaFilePath, 'r', encoding='utf-8') as f:
            content = f.read()
            climate_data_dict = self.lua_env.load_lua_content(content)
            self.assertEqual(1, len(climate_data_dict))
            self.assertIn('data', climate_data_dict)
            self.assertIn('LightOnTime', climate_data_dict['data'])
            self.assertEqual(climate_data_dict['data']['LightOnTime']['ID'], "LightOnTime")
            self.assertEqual(climate_data_dict['data']['LightOnTime']['Type'], "Str()")
            self.assertEqual(climate_data_dict['data']['LightOnTime']['Value'], "18:00:00")

            self.assertIn('DefaultRegionName', climate_data_dict['data'])
            self.assertEqual(climate_data_dict['data']['DefaultRegionName']['ID'], "DefaultRegionName")
            self.assertEqual(climate_data_dict['data']['DefaultRegionName']['Type'], "Str()")
            self.assertIsInstance(climate_data_dict['data']['DefaultRegionName']['Value'], LuaLangStringWrapper)

    
    def test_string_cn_data_large(self):
        luaFilePath = "/app/p4WorkSpace/C7/Development/Mainline/Client/Content/Script/Data/Excel/LanguageData/StringDB_CN_Data.lua#17643"
        with open(luaFilePath, 'r', encoding='utf-8') as f:
            content = f.read()
            string_data_dict = self.lua_env.load_lua_content(content, luaFilePath)
            self.assertEqual(1, len(string_data_dict))
            self.assertIn('data', string_data_dict)
            return string_data_dict

    def test_string_cn_data_short(self):
        luaFilePath = "/app/p4WorkSpace/C7/Development/Mainline/Client/Content/Script/Data/Excel/LanguageData/StringDB.lua#1"
        with open(luaFilePath, 'r', encoding='utf-8') as f:
            content = f.read()
            string_data_dict = self.lua_env.load_lua_content(content, luaFilePath)
            self.assertEqual(1, len(string_data_dict))
            self.assertIn('data', string_data_dict)
            return string_data_dict

def doTest():
    # 不能直接调用unittest.main，docker会退出
    # unittest.main()
    test_lua_case = TestLuaCase()
    test_lua_case.setUp()
    test_lua_case.test_climate_data()
    test_lua_case.test_string_cn_data_short()
    test_lua_case.test_string_cn_data_large()

# from myUnitTest import testLua
# testLua.doTest()

if __name__ == '__main__':
    doTest()
