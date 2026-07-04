# 部分常用执行列表：
# doBroadcastCmd("import g;g.flag = 'vvv'")
# doBroadcastCmd("import config;config.CUR_SERVER_NAME = 'czx'")
# doBroadcastCmd("import config;config.CUR_SERVER_NAME = 'obt-a'")

# doBroadcastCmd("import config;config.CUR_SERVER_NAME = 'preonline-a'")
# doBroadcastCmd("from utility import const;const.RANK_CHEAT_PUNISH_THRESHOLD = 1")

def doBroadcastCmd(cmd):
    from dbImp.redisImp import my_redis, CMD_CHANNEL_NAME
    my_redis.publish(CMD_CHANNEL_NAME, cmd)

def testCurrent():
    from Implement.hotfixImpl import luaImp
    lua_env = luaImp.LuaEnv()
    lua_env.prepare_env()
    server_file_path = "/app/p4WorkSpace/C7/Development/Mainline/Server/script_lua/Logic/Entities/Group_Function_20260122_095318_37693563.lua"
    with open(server_file_path, 'r', encoding='utf-8') as f:
        file_content = f.read() 
        data1 = lua_env.load_lua_content(file_content , "xxx")
        return data1
