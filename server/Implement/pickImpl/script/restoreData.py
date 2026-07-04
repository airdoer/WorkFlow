import json
import sys
import argparse
from log import print_error, print_warn
import mongoImportUtils 
import databaseUtils

CONF_PATH = "/app/Implement/pickImpl/config/local_conf.json"

def restore_file(server, target_account, file_path):
    # ===== 加载配置 =====
    with open(CONF_PATH, "r", encoding="utf-8") as f:
        conf = json.load(f)

    # ===== 连接数据库 =====
    if server not in conf:
        print_error("找不到对应Server，请检查参数")
        sys.exit(1)
    
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

    print("开始导出")
    if not mongoImportUtils.restore_from_file(target_db, file_path, target_account):
        print_error("restore 失败")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="dump目标数据库玩家数据")
    parser.add_argument('-ts', '--targetserver', help='目标服务器')
    parser.add_argument('-ta', '--targetaccount', help='目标账号')
    parser.add_argument('-fp', '--filepath', help='文件位置')
    
    args = parser.parse_args()
    
    if not args.targetserver:
        print("错误: 必须同时指定目标服务器")
        return 1
    
    args.targetaccount = args.targetaccount or "test"

    # 更新配置文件
    success = restore_file(
        args.targetserver,
        args.targetaccount,
        args.filepath, 
    )
    
    if success:
        print("restore 数据成功")
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit(main())