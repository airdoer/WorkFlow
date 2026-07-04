from Implement.pickImpl.script.log import print_error, print_info
from pymongo import MongoClient
from bson.raw_bson import RawBSONDocument
import json

mongoClient = {}

# ===== 连接单个逻辑服的mongo =====
def mongoClientConnectLogic(conf, name):
    uri = f"mongodb://{conf['username']}:{conf['password']}@{conf['hosts'][0]}/?authSource={conf['auth_source']}&readPreference=primary&ssl=false&directConnection=true"
    print_info(f"mongo {name} uri:{uri}")
    client = MongoClient(uri, document_class=RawBSONDocument)
    return client[name]


# ===== 连接整个服的mongo
def mongoClientConnectServer(conf):
    mongo_cluster = conf["mongo_cluster"]

    connections = {}
    # 共享logic
    shared_name = conf["shared_database"]
    connections[0] = mongoClientConnectLogic(mongo_cluster[shared_name], shared_name)

    for id, name in conf["logic_server_database"].items():
        connections[id] = mongoClientConnectLogic(mongo_cluster[name], name)
    
    return connections


# ===== 从本地配置中获取mongo配置 =====
def getLocalMongoConf(conf_path):
    with open(conf_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    dbmgr = data.get("dbmgr", {})
    mongo_cluster = dbmgr.get("mongo_cluster", {})
    logic = data.get("logic", {})

    return {
        "mongo_cluster": mongo_cluster,
        "shared_database": logic["database"],
        "logic_server_database": logic["logic_server_database"]
    }


# ===== 连接所有的mongo =====
def mongoClientConnect(conf, local_conf_path, src_name, dst_name):
    if src_name not in conf:
        print_error(f"src mongo {src_name} not found in conf")
        return False

    mongoClient[src_name] = mongoClientConnectServer(conf[src_name])

    if dst_name in conf:
        mongoClient[dst_name] = mongoClientConnectServer(conf[dst_name])
    else:
        dst_conf = getLocalMongoConf(local_conf_path)
        if not dst_conf:
            return False
        else:
            mongoClient[dst_name] = mongoClientConnectServer(dst_conf)

    return True


# ==== 获取对应的db连接 =====
def getMongoClientByLogicID(server_name, logicID):
    if server_name not in mongoClient:
        return None
    elif logicID not in mongoClient[server_name]:
        return None
    else:
        return mongoClient[server_name][logicID]
