import json
import os
import sys
from Implement.pickImpl.script.log import print_error, print_warn
import mongoImportUtils 
import databaseUtils

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PICK_IMPL_DIR = os.path.dirname(SCRIPT_DIR)
CONF_PATH = os.path.join(PICK_IMPL_DIR, "config", "conf.json")

# ===== 加载配置 =====
with open(CONF_PATH, "r", encoding="utf-8") as f:
    conf = json.load(f)

# ===== 加载collection_info =====
with open(conf["collection_info_path"], "r", encoding="utf-8") as f:
    collection_config = json.load(f)

# ===== 加载service_base =====
with open(conf["service_base_path"], "r", encoding="utf-8") as f:
    service_config = json.load(f)

DEFAULT_SRC_NAME = conf.get("SourceEnvironmont", "local")
DEFAULT_DST_NAME = conf.get("DestEnvironmont", "local")

# ===== 连接数据库 =====
if not databaseUtils.mongoClientConnect(conf["db"], conf["config_path"], DEFAULT_SRC_NAME, DEFAULT_DST_NAME):
    print_error("mongoClientConnect failed")
    sys.exit(1)

src_db = databaseUtils.getMongoClientByLogicID(DEFAULT_SRC_NAME, conf["src_logic_id"])
src_shared_db = databaseUtils.getMongoClientByLogicID(DEFAULT_SRC_NAME, 0)
dst_db = databaseUtils.getMongoClientByLogicID(DEFAULT_DST_NAME, conf["dst_logic_id"])
dst_shared_db = databaseUtils.getMongoClientByLogicID(DEFAULT_DST_NAME, 0)


dump_file = os.path.join(PICK_IMPL_DIR, "data", "dump.json")
dest_account = conf.get("DestAccount", "")
print("数据迁移开始")
print("开始导出")
if not mongoImportUtils.dump_to_file(src_db, conf, service_config, dump_file):
    print_error("dump JSON 失败")
    sys.exit(1)

print("开始导入")
if not mongoImportUtils.restore_from_file(dst_db, dump_file, dest_account):
    print_error("restore JSON 失败")
    sys.exit(1)

print("🎉 数据迁移完成！")

