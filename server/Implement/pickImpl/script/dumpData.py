import json
import sys
import argparse
from log import print_error, print_warn
import mongoImportUtils 
import databaseUtils

CONF_PATH = "/app/Implement/pickImpl/config/new_conf.json"
SERVICE_BASE_PATH = "/app/Implement/pickImpl/config/service_base.json"

def dump_file(server, avatarid, shortuid, file_path):
    # ===== 加载配置 =====
    with open(CONF_PATH, "r", encoding="utf-8") as f:
        conf = json.load(f)

    # ===== 加载service_base =====
    with open(SERVICE_BASE_PATH, "r", encoding="utf-8") as f:
        service_config = json.load(f)

    # ===== 连接数据库 =====
    if server not in conf:
        print_error("找不到对应Server，请检查参数")
        sys.exit(1)
    
    avatar_list = avatarid.split(',')
    short_uid = shortuid.split(',')

    db_info = {}
    for data in conf[server]:
        if data['group_type'] == "mongodb":
            db_info['username'] = data['username']
            db_info['password'] = data['password']
            db_info['hosts'] = data['hosts']
            db_info['auth_source'] = data['auth_source']
            break
    
    target_db = databaseUtils.mongoClientConnectLogic(db_info, server)
    if target_db is None:
        print_error("连接数据库失败！")
        sys.exit(1)

    dump_conf = {
        "Account": [],
        "AvatarID": avatar_list,
        "ShortUID": short_uid,
        "Service": [],
        "Collection": {},
    }
    print("开始导出")
    if not mongoImportUtils.dump_to_file(target_db, dump_conf, service_config, file_path):
        print_error("dump JSON 失败")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="dump目标数据库玩家数据")
    parser.add_argument('-ts', '--targetserver', help='目标服务器')
    parser.add_argument('-ta', '--targetavatarid', help='目标玩家（多个用逗号分隔）')
    parser.add_argument('-fp', '--filepath', help='文件位置')
    
    args = parser.parse_args()
    
    if not args.targetserver or not args.targetavatarid:
        print("错误: 必须同时指定目标服务器和目标玩家")
        return 1
    
    # 更新配置文件
    success = dump_file(
        args.targetserver,
        args.targetavatarid,
        args.filepath, 
    )
    
    if success:
        print("dump 数据成功")
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit(main())