import redis  # 导入redis 模块
import rediscluster
import config
import json
import os
from data import AllVectorIDMap
from datetime import datetime, timedelta
from utility import const
import base64
import threading


if config.cluster:
    pool = rediscluster.ClusterConnectionPool(host=config.redis_host, port=config.redis_port, decode_responses=True,
                                              password=config.password)
    my_redis = rediscluster.RedisCluster(connection_pool=pool)
else:
    pool = redis.ConnectionPool(host=config.redis_host, port=config.redis_port, decode_responses=True,
                                password=config.password)
    my_redis = redis.Redis(connection_pool=pool)

MEMORY_TYPES = "MEMORY_TYPES"
MEMORY_KEY_FORMAT = "{memory}_MemoryStatistic_%s"
MEMORY_FILED_KEY_FORMAT = "{memory_field}_%s"
MEMORY_COUNT_KEY_FORMAT = "memory_count_%s_%s"
MEMORY_GAMES_KEY_FORMAT = "memory_games_%s_%s"

TRAFFIC_TYPES = "TRAFFIC_TYPES"
TRAFFIC_KEY_FORMAT = "{traffic}_TrafficStatistic_%s"
TRAFFIC_FILED_KEY_FORMAT = "{traffic_field}_%s"
TRAFFIC_TOTAL_RECV_KEY_FORMAT = "{traffic_total_recv}_%s"
TRAFFIC_TOTAL_SEND_KEY_FORMAT = "{traffic_total_send}_%s"

CONSIST_KEY = "C1_CONSIST_STATISTIC"

CONSIST_ACC_KEY_0 = "C1_CONSIST_ACC_STATISTIC_0"
CONSIST_ACC_KEY_1 = "C1_CONSIST_ACC_STATISTIC_1"

BATTLE_ACC_KEY = "C1_BATTLE_ACC_STATISTIC"

# review的优先battleId列表
BATTLE_REVIEW_UP_SET_KEY = "C1_BATTLE_REVIEW_UP_SET"

HOTFIX_RESOURCE_SET_KEY = "C1_HOTFIX_RESOURCE_KEY"

HOTFIX_RESOURCE_KEY_PREFIX = "C1_HOTFIX_RESOURCE:"

RANK_BATTLE_RECORD_KEY = "C1_RANK_RECORD_"

REVIEW_PLAYER_COUNT_KEY = "C1_REVIEW_PLAYER_COUNT_"

REVIEW_PLAYER_RANKIDS_KEY = "C1_REVIEW_PLAYER_RANKIDS_"

AUTO_DEL_RANK_RECORD_KEY = "C1_AUTO_DEL_RANK_SET"

AUTO_RANK_FALSE_ACC_KEY = "C1_AUTO_FALSE_ACC"

AUTO_RANK_FALSE_ACC_LUA_SCRIPT = """
    local count = redis.call('INCR', KEYS[1])  -- 计数 +1
    redis.call('EXPIRE', KEYS[1], ARGV[1])    -- 刷新过期时间
    return count  -- 返回当前计数
"""

REDIS_GAME_FLAG_EXPIRE_TIME = 3 * 24 * 3600
UPDATE_THRESHOLD = 100
memoryFields = {}
memoryDetailGames = {}
memoryDefaultDict = {}
memoryMaxInfoDict = {}
memoryDefaultUpdateDict = {}
memoryMaxInfoUpdateDict = {}
memoryIter = 0
trafficFields = {}
trafficIter = 0


CMD_CHANNEL_NAME = 'broadcast_cmd_channel'


def redis_subscriber():
    pubsub = my_redis.pubsub()
    pubsub.subscribe(CMD_CHANNEL_NAME)
    print(f"Subscribed to channel: {CMD_CHANNEL_NAME}")

    for message in pubsub.listen():
        if message['type'] == 'message':
            handle_broadcast(message['data'])


def handle_broadcast(cmd):
    print(f"Received broadcast command: {cmd}")
    import g
    g.last_cmd = cmd
    exec(cmd, globals())


threading.Thread(target=redis_subscriber, daemon=True).start()


class RedisLock:
    def __init__(self, redis_client, lock_name, expire_time=30):
        self.redis = redis_client
        self.lock_name = lock_name
        self.expire_time = expire_time

    def acquire(self):
        return self.redis.set(self.lock_name, "locked", nx=True, ex=self.expire_time)

    def release(self):
        self.redis.delete(self.lock_name)


def getRedisLock(lock_name):
    return RedisLock(my_redis, lock_name)


def addRankRecord(battleId, playerId, rankId):
    # battleId='724985e6c35a11ef8e0f415dd7f4ee36' playerId='480129360' rankId='official_100200008'
    # 设置battleId->(playerId和rankId)的记录，设置有效时间为4个小时
    # self.redis.setex(RANK_BATTLE_RECORD_KEY + battleId, RANK_BATTLE_VALID_TIME, playerId + "_" + rankId)
    key = RANK_BATTLE_RECORD_KEY + battleId
    value = f"{playerId}:{rankId}"
    my_redis.setex(key, const.RANK_BATTLE_VALID_TIME, value)


def setRankBattleCheat(battleId):
    # battle被发现是作弊，需要查找其是否在RANK_BATTLE_RECORD中，如果在，找到playerId和rankId
    # 然后记录到REVIEW_PLAYER_COUNT_KEY和REVIEW_PLAYER_RANKIDS_KEY
    # 返回playerId
    rank_record_key = RANK_BATTLE_RECORD_KEY + battleId
    value = my_redis.get(rank_record_key)
    if not value:
        return None
    # 提取 playerId 和 rankId
    playerId, rankId = value.split(":", 1)
    # 更新玩家被标记次数
    player_count_key = REVIEW_PLAYER_COUNT_KEY + playerId
    my_redis.incr(player_count_key)
    count = my_redis.eval(AUTO_RANK_FALSE_ACC_LUA_SCRIPT, 1, AUTO_RANK_FALSE_ACC_KEY, const.RANK_CHEAT_FALSE_TIME_VALID_TIME)
    if count > const.RANK_CHEAT_FALSE_THRESHOLD:
        # 短时间内作弊不一致次数超过阈值，不进行自动下榜操作
        print(f'redisImp setRankBattleCheat Failed: THRESHOLD {count} > {const.RANK_CHEAT_FALSE_THRESHOLD}')
        return None

    # 添加 rankId 到玩家的 rankId 列表
    player_rankids_key = REVIEW_PLAYER_RANKIDS_KEY + playerId
    my_redis.delete(rank_record_key)
    rankBattleId = f"{rankId}:{battleId}"
    my_redis.sadd(player_rankids_key, rankBattleId)
    return playerId


def checkPlayerCheckCount(playerId):
    # 如果count超过阈值，就查找playerId和rankIds，打印日志
    player_count_key = REVIEW_PLAYER_COUNT_KEY + playerId
    player_rankids_key = REVIEW_PLAYER_RANKIDS_KEY + playerId
    # 获取玩家被标记的次数
    count = int(my_redis.get(player_count_key) or 0)
    if count < const.RANK_CHEAT_PUNISH_THRESHOLD:
        return []
    # 获取玩家所有的 rankId
    rankBattleInfos = my_redis.smembers(player_rankids_key)
    rankBattleInfos = list(rankBattleInfos)
    print(f"玩家 {playerId} 被标记作弊次数超过阈值：{count} 次，关联 RankIds：{rankBattleInfos}")
    return rankBattleInfos


def clearPlayerCheckCount(playerId):
    player_count_key = REVIEW_PLAYER_COUNT_KEY + playerId
    player_rankids_key = REVIEW_PLAYER_RANKIDS_KEY + playerId
    # 清空玩家的被标记次数和 rankId 列表
    my_redis.delete(player_count_key, player_rankids_key)


def addAutoDelRankRecord(playerId, rankBattleIds):
    curTs = datetime.now().timestamp()
    data = {
        "player": playerId,
        "rankBattleIds": rankBattleIds,
        "time": curTs
    }
    # 使用时间戳作为排序依据，存入 Redis 的有序集合
    my_redis.zadd(AUTO_DEL_RANK_RECORD_KEY, {json.dumps(data): curTs})
    # 限制集合最大长度为 1000，移除最老的多余数据
    my_redis.zremrangebyrank(AUTO_DEL_RANK_RECORD_KEY, 0, -1001)


def getAutoDelRankRecords():
    data = my_redis.zrange(AUTO_DEL_RANK_RECORD_KEY, 0, -1)
    return [json.loads(item) for item in data]


def addBattleStatistic(player_counts: int, consist_status: bool, start_time: float, game_id: str, use_battle_server):
    game = my_redis.get(game_id)
    if game:
        return

    my_redis.set(game_id, 1, ex=REDIS_GAME_FLAG_EXPIRE_TIME)
    my_redis.incr(BATTLE_ACC_KEY, 1)
    if player_counts >= 2 and not use_battle_server:
        # 形式如下:
        # score: 1689268660
        # member: 1689268660.0_1
        _map = {f"{game_id}_{int(consist_status)}": start_time}
        my_redis.zadd(CONSIST_KEY, _map)
        if consist_status:
            my_redis.incr(CONSIST_ACC_KEY_1, 1)
        else:
            my_redis.incr(CONSIST_ACC_KEY_0, 1)


def clearHotfix():
    hotfixNames = my_redis.smembers(HOTFIX_RESOURCE_SET_KEY)
    print("All Hotfix Names:", hotfixNames)

    for hotfixName in hotfixNames:
        my_redis.delete(f"{HOTFIX_RESOURCE_KEY_PREFIX}{hotfixName}")
        my_redis.srem(HOTFIX_RESOURCE_SET_KEY, hotfixName)


def addHotfix(resourceHotfixInfo):
    for hotfixName, hotfixValue in resourceHotfixInfo.items():
        resourcePath, hotfixContent = hotfixValue
        my_redis.hset(f"{HOTFIX_RESOURCE_KEY_PREFIX}{hotfixName}", "resourcePath", resourcePath)
        # hotfixContent对于二进制资源来说是bytes类型的,需要变成str,为了让redis取值的时候不报错,因为decode_responses为True
        hotfixContentStr = base64.b64encode(hotfixContent).decode()
        my_redis.hset(f"{HOTFIX_RESOURCE_KEY_PREFIX}{hotfixName}", "hotfixContent", hotfixContentStr)
        my_redis.sadd(HOTFIX_RESOURCE_SET_KEY, hotfixName)


def getAllHotfix():
    hotfixNames = my_redis.smembers(HOTFIX_RESOURCE_SET_KEY)
    if not hotfixNames:
        return {"error": "No hotfixes found"}

    all_hotfixes = {}
    for name in hotfixNames:
        resource_path = my_redis.hget(f"{HOTFIX_RESOURCE_KEY_PREFIX}{name}", "resourcePath")
        hotfix_content = my_redis.hget(f"{HOTFIX_RESOURCE_KEY_PREFIX}{name}", "hotfixContent")
        all_hotfixes[name] = {
            "resourcePath": resource_path,
            "hotfixContent": hotfix_content
        }
    return all_hotfixes


def getHotfix(hotfixName):
    if not my_redis.exists(f"{HOTFIX_RESOURCE_KEY_PREFIX}{hotfixName}"):
        return {"error": f"Hotfix not found '{hotfixName}'"}

    resource_path = my_redis.hget(f"{HOTFIX_RESOURCE_KEY_PREFIX}{hotfixName}", "resourcePath")
    hotfix_content = my_redis.hget(f"{HOTFIX_RESOURCE_KEY_PREFIX}{hotfixName}", "hotfixContent")

    return {
        "name": hotfixName,
        "resourcePath": resource_path,
        "hotfixContent": hotfix_content
    }


def syncHotfixList(hotfixNameList):
    hotfixNames = my_redis.smembers(HOTFIX_RESOURCE_SET_KEY)
    if not hotfixNames:
        return {}

    retHotfixInfo = {}
    for hotfixName in hotfixNames:
        if hotfixName not in hotfixNameList:
            resource_path = my_redis.hget(f"{HOTFIX_RESOURCE_KEY_PREFIX}{hotfixName}", "resourcePath")
            hotfix_content = my_redis.hget(f"{HOTFIX_RESOURCE_KEY_PREFIX}{hotfixName}", "hotfixContent")
            retHotfixInfo[hotfixName] = {
                "resourcePath": resource_path,
                "hotfixContent": hotfix_content
            }
    return retHotfixInfo


def upCheckBattleId(battle_id: str):
    # 优先设置机器校验
    my_redis.sadd(BATTLE_REVIEW_UP_SET_KEY, battle_id)


def getCheckBattleId():
    # 这里暂不考虑多进程读写问题
    battleId = my_redis.spop(BATTLE_REVIEW_UP_SET_KEY)
    return battleId


def inputCheckBattleIds(battleIds: list):
    for battleId in battleIds:
        my_redis.sadd(BATTLE_REVIEW_UP_SET_KEY, battleId)


def getConsistStatistic():
    end_time = datetime.now().timestamp()
    one_hour_start_time = end_time - 60 * 60
    one_hour_results = [0, 0, 0]  # 一致战场，总战场，一致率
    consistList = my_redis.zrangebyscore(CONSIST_KEY, one_hour_start_time, end_time)
    if consistList:
        consistList = [x.split('_')[-1] for x in consistList]
        one_hour_results[1] = len(consistList)
        one_hour_results[0] = consistList.count('1')
        one_hour_results[2] = one_hour_results[0] / one_hour_results[1]
    v1, v0, vAll = my_redis.mget(CONSIST_ACC_KEY_1, CONSIST_ACC_KEY_0, BATTLE_ACC_KEY)
    v0 = int(v0) if v0 else 0
    v1 = int(v1) if v1 else 0
    vAll = int(vAll) if vAll else 0
    all_results = [v1, v0+v1, 0 if not (v0+v1) else v1 / (v0+v1)]

    return {
        '1hConsist': one_hour_results,
        'allConsist': all_results,
        'allBattle': vAll
    }


# 将数据保存到Redis中
def save_to_redis(mock_data_game):
    for game in mock_data_game:
        my_redis.set(game, json.dumps(mock_data_game[game]))
        my_redis.sadd(mock_data_game[game]["edition"], mock_data_game[game]["id"])
        my_redis.zadd("playerCounts", mock_data_game[game]["id"], mock_data_game[game]["playerCounts"])


# 获取所有的对局信息
def get_all_game_data():
    games_data = {}
    for game in my_redis.keys("game:*"):
        games_data[game] = json.loads(my_redis.get(game))
    return games_data


# 清空数据库
def flush_db():
    my_redis.flushdb()


# 获取指定版本的对局信息
def get_edition_game_data(edition):
    games_data = {}
    for game_id in my_redis.smembers(edition):
        game = "game:" + game_id
        games_data[game] = json.loads(my_redis.get(game))
    return games_data


# 获取指定id的对局信息
def get_id_game_data(id):
    game = json.loads(my_redis.get("game:" + id))
    return game


# 获取指定最少玩家数量以上的对局信息
def get_player_counts_game_data(counts):
    ids = my_redis.zrangebyscore("playerCounts", counts, 999)
    games_data = {}
    for game_id in ids:
        game = "game:" + game_id
        games_data[game] = json.loads(my_redis.get(game))
    return games_data


def clearOverTimeConsistStatistic():
    # 清理两个小时前的consistKey
    early_time = datetime.now().timestamp() - 60 * 60 * 2
    my_redis.zremrangebyscore(CONSIST_KEY, 0, early_time)


def clearConsistStatistic():
    clearOverTimeConsistStatistic()
    my_redis.set(BATTLE_ACC_KEY, 0)
    my_redis.set(CONSIST_ACC_KEY_1, 0)
    my_redis.set(CONSIST_ACC_KEY_0, 0)


def addMemoryData(inputMemoryData, gameId, battle_type):
    global memoryFields
    global memoryDetailGames
    global memoryDefaultDict
    global memoryMaxInfoDict
    global memoryDefaultUpdateDict
    global memoryMaxInfoUpdateDict
    my_redis.sadd(MEMORY_TYPES, battle_type)
    memory_key = MEMORY_KEY_FORMAT % (battle_type, )
    memory_field_key = MEMORY_FILED_KEY_FORMAT % (battle_type, )
    print(f'redisImp memoryData {gameId} {battle_type}')
    memoryData = {}

    keys = []
    for k, v in inputMemoryData.items():
        if not isinstance(k, str):
            continue
        idx = k.rfind('_')
        k_name = k[:idx]
        default_value = int(k[idx+1:])
        if k_name not in AllVectorIDMap.data:
            keys.append(k_name)
        memoryData[f'{k_name}_max'] = int(v)
        memoryData[f'{k_name}_default'] = default_value
        memoryData[f'{k_name}_gameId'] = gameId
    for k in AllVectorIDMap.data:
        keys.append(k)

    for k in keys:
        k_max = f'{k}_max'
        if k_max in memoryData:
            val = memoryData[k_max]
            memory_count_key = MEMORY_COUNT_KEY_FORMAT % (battle_type, k)
            count = my_redis.hget(memory_count_key, val)
            if not count:
                count = 0
            my_redis.hset(memory_count_key, val, int(count) + 1)
            memory_games_key = MEMORY_GAMES_KEY_FORMAT % (battle_type, k)
            memoryDetailGames.setdefault(memory_games_key, {})
            memoryDetailGames[memory_games_key][val] = gameId

    for k in keys:
        memoryFields.setdefault(memory_field_key, {})
        memoryFields[memory_field_key][k] = True
        k_default = f'{k}_default'
        k_max = f'{k}_max'
        k_gameId = f'{k}_gameId'
        if not memoryDefaultDict.get(memory_key) or \
                (k_default in memoryData and int(memoryDefaultDict[memory_key].get(k_default, 0)) != memoryData[k_default]):
            memoryDefaultDict.setdefault(memory_key, {})
            memoryDefaultDict[memory_key].update({k_default: memoryData.get(k_default, AllVectorIDMap.data.get(k, 0))})
            memoryDefaultUpdateDict.setdefault(memory_key, {})
            memoryDefaultUpdateDict[memory_key].update({k_default: memoryData.get(k_default, AllVectorIDMap.data.get(k, 0))})
        if not memoryMaxInfoDict.get(memory_key) or \
                (k_max in memoryData and int(memoryMaxInfoDict[memory_key].get(k_max, 0)) <= memoryData[k_max]):
            memoryMaxInfoDict.setdefault(memory_key, {})
            memoryMaxInfoDict[memory_key][k] = {k_max: memoryData.get(k_max, 0), k_gameId: memoryData.get(k_gameId, '')}
            memoryMaxInfoUpdateDict.setdefault(memory_key, {})
            memoryMaxInfoUpdateDict[memory_key][k] = {k_max: memoryData.get(k_max, 0), k_gameId: memoryData.get(k_gameId, '')}
    _onAddMemoryData()


def _onAddMemoryData():
    global memoryFields
    global memoryDetailGames
    global memoryDefaultUpdateDict
    global memoryMaxInfoUpdateDict
    global memoryIter
    memoryIter += 1
    if memoryIter >= UPDATE_THRESHOLD:
        for k in memoryFields:
            v = list(memoryFields[k])
            memoryFields[k] = {}
            if v:
                my_redis.sadd(k, *v)
        for k in memoryDetailGames:
            v = memoryDetailGames[k]
            memoryDetailGames[k] = {}
            if v:
                my_redis.hmset(k, v)
        for k in memoryDefaultUpdateDict:
            v = memoryDefaultUpdateDict[k]
            memoryDefaultUpdateDict[k] = {}
            if v:
                my_redis.hmset(k, v)
        for k, v in memoryMaxInfoUpdateDict.items():
            memory = my_redis.hgetall(k)
            memoryInfo = {}
            for k2, v2 in v.items():
                k_max = f'{k2}_max'
                k_gameId = f'{k2}_gameId'
                if not memory or int(memory.get(k_max, 0)) <= v2[k_max]:
                    memoryInfo.update({k_max: v2[k_max], k_gameId: v2[k_gameId]})
            memoryMaxInfoUpdateDict[k] = {}
            if memoryInfo:
                my_redis.hmset(k, memoryInfo)
        memoryIter = 0


def getMemoryDetailData(battle_type):
    resData = {}
    memory_field_key = MEMORY_FILED_KEY_FORMAT % (battle_type, )
    fields = my_redis.smembers(memory_field_key)
    for field in fields:
        resData[field] = {}
        memory_count_key = MEMORY_COUNT_KEY_FORMAT % (battle_type, field)
        memory_games_key = MEMORY_GAMES_KEY_FORMAT % (battle_type, field)
        sizes = my_redis.hkeys(memory_count_key)
        for size in sizes:
            info = {
                "count": my_redis.hget(memory_count_key, size),
                "gameId": my_redis.hget(memory_games_key, size),
            }
            resData[field][size] = info
    return resData


def renderMemoryData(memoryData, fields):
    ret_list = []
    for k in fields:
        ret_list.append({
            "type": "default",
            "object": k,
            "value": int(float(memoryData.get(f'{k}_default', 0))),
            "gameId": memoryData.get(f'{k}_gameId', 0)
        })
        ret_list.append({
            "type": "max",
            "object": k,
            "value": int(float(memoryData.get(f'{k}_max', 0))),
            "gameId": memoryData.get(f'{k}_gameId', 0)
        })
    return ret_list


def getMemoryData(battle_type=None):
    resData = {"battleType": []}
    if battle_type:
        types = [battle_type]
    else:
        types = my_redis.smembers(MEMORY_TYPES)
    for type in types:
        memory_key = MEMORY_KEY_FORMAT % (type, )
        memory = my_redis.hgetall(memory_key)
        memory_field_key = MEMORY_FILED_KEY_FORMAT % (type, )
        fields = my_redis.smembers(memory_field_key)
        resData[type] = renderMemoryData(memory, fields)
        resData["battleType"].append({"id": type})
    return resData


def deleteMemoryData(battle_type=None):
    if battle_type:
        _deleteMemoryDataByType(battle_type)
        return "deleteMemoryData return"
    types = my_redis.smembers(MEMORY_TYPES)
    for type in types:
        _deleteMemoryDataByType(type)
    return "deleteMemoryData return"


def _deleteMemoryDataByType(battle_type):
    _saveMemoryData(battle_type)
    memory_key = MEMORY_KEY_FORMAT % (battle_type, )
    my_redis.delete(memory_key)
    memory_field_key = MEMORY_FILED_KEY_FORMAT % (battle_type, )
    fields = my_redis.smembers(memory_field_key)
    for field in fields:
        memory_count_key = MEMORY_COUNT_KEY_FORMAT % (battle_type, field)
        memory_games_key = MEMORY_GAMES_KEY_FORMAT % (battle_type, field)
        my_redis.delete(memory_count_key)
        my_redis.delete(memory_games_key)
    my_redis.delete(memory_field_key)
    my_redis.srem(MEMORY_TYPES, battle_type)


def _saveMemoryData(battle_type, update_minutes=120):
    filename = f'memory-{battle_type}.json'
    if os.path.exists(filename):
        last_modified_time = datetime.fromtimestamp(os.path.getmtime(filename))
        time_difference = datetime.now() - last_modified_time
        if time_difference <= timedelta(minutes=update_minutes):
            return
    data = json.dumps(getMemoryData(battle_type))
    with open(filename, 'w+') as f:
        f.write(data)


def addTrafficData(inputTrafficData, gameId, battle_type):
    global trafficFields
    duration = inputTrafficData.get('duration', 0)
    print(f'redisImp trafficData {gameId=} {battle_type=} {duration=}')
    if not duration:
        return

    my_redis.sadd(TRAFFIC_TYPES, battle_type)
    traffic_recv_key = TRAFFIC_TOTAL_RECV_KEY_FORMAT % (battle_type, )
    val = inputTrafficData.get('recvDataLength', 0) / duration
    _updateTotalTrafficData(traffic_recv_key, val, gameId)
    traffic_send_key = TRAFFIC_TOTAL_SEND_KEY_FORMAT % (battle_type, )
    val = inputTrafficData.get('sendDataLength', 0) / duration
    _updateTotalTrafficData(traffic_send_key, val, gameId)

    traffic_field_key = TRAFFIC_FILED_KEY_FORMAT % (battle_type, )
    traffic_key = TRAFFIC_KEY_FORMAT % (battle_type, )
    traffics = my_redis.hgetall(traffic_key)
    trafficInfo = {}
    trafficData = inputTrafficData.get('viewCommandData', {})
    for k, v in trafficData.items():
        if not isinstance(k, str):
            continue
        trafficFields.setdefault(traffic_field_key, {})
        trafficFields[traffic_field_key][k] = True
        k_sum = f'{k}_sum'
        k_count = f'{k}_count'
        k_max = f'{k}_max'
        k_gameId = f'{k}_gameId'
        val = float(v) / duration
        oldSum = float(traffics.get(k_sum, 0))
        oldCount = int(traffics.get(k_count, 0))
        trafficInfo.update({k_sum: oldSum + val, k_count: oldCount + 1})
        if not traffics or float(traffics.get(k_max, 0)) <= val:
            trafficInfo.update({k_max: val, k_gameId: gameId})
    if trafficInfo:
        my_redis.hmset(traffic_key, trafficInfo)
    _onAddTrafficData()


def _updateTotalTrafficData(key, val, gameId):
    totalTraffics = my_redis.hgetall(key)
    totalTrafficInfo = {}
    oldTotalRecvSum = float(totalTraffics.get('sum', 0))
    oldTotalRecvCount = int(totalTraffics.get('count', 0))
    totalTrafficInfo.update({'sum': oldTotalRecvSum + val, 'count': oldTotalRecvCount + 1})
    if not totalTraffics or float(totalTraffics.get('max', 0)) <= val:
        totalTrafficInfo.update({'max': val, 'gameId': gameId})
    if totalTrafficInfo:
        my_redis.hmset(key, totalTrafficInfo)


def _onAddTrafficData():
    global trafficFields
    global trafficMaxInfoUpdateDict
    global trafficIter
    trafficIter += 1
    if trafficIter >= UPDATE_THRESHOLD:
        for k in trafficFields:
            v = list(trafficFields[k])
            trafficFields[k] = {}
            if v:
                my_redis.sadd(k, *v)
        trafficIter = 0


def renderTrafficData(trafficData, fields):
    ret_list = []
    for k in fields:
        gameId = trafficData.get(f'{k}_gameId', 0)
        ret_list.append({
            "type": "avg",
            "object": k,
            "value": int(float(trafficData.get(f'{k}_max', 0))),
            "gameId": gameId
        })
        ret_list.append({
            "type": "max",
            "object": k,
            "value": int(float(trafficData.get(f'{k}_sum', 0)) / int(trafficData.get(f'{k}_count', 1))),
            "gameId": gameId
        })
    return ret_list


def getTrafficData(battle_type=None):
    resData = {"battleType": []}
    if battle_type:
        types = [battle_type]
    else:
        types = my_redis.smembers(TRAFFIC_TYPES)
    for type in types:
        traffic_key = TRAFFIC_KEY_FORMAT % (type, )
        traffics = my_redis.hgetall(traffic_key)
        traffic_field_key = TRAFFIC_FILED_KEY_FORMAT % (type, )
        fields = my_redis.smembers(traffic_field_key)
        resData[type] = renderTrafficData(traffics, fields)
        traffic_recv_key = TRAFFIC_TOTAL_RECV_KEY_FORMAT % (type, )
        traffic_send_key = TRAFFIC_TOTAL_SEND_KEY_FORMAT % (type, )
        resData[f'{type}_recv'] = my_redis.hgetall(traffic_recv_key)
        resData[f'{type}_send'] = my_redis.hgetall(traffic_send_key)
        resData["battleType"].append({"id": type})
    return resData


def deleteTrafficData(battle_type=None):
    if battle_type:
        _deleteTrafficDataByType(battle_type)
        return "deleteTrafficData return"
    types = my_redis.smembers(TRAFFIC_TYPES)
    for type in types:
        _deleteTrafficDataByType(type)
    return "deleteTrafficData return"


def _deleteTrafficDataByType(battle_type):
    _saveTrafficData(battle_type)
    traffic_key = TRAFFIC_KEY_FORMAT % (battle_type, )
    my_redis.delete(traffic_key)
    traffic_field_key = TRAFFIC_FILED_KEY_FORMAT % (battle_type, )
    my_redis.delete(traffic_field_key)
    traffic_recv_key = TRAFFIC_TOTAL_RECV_KEY_FORMAT % (battle_type, )
    traffic_send_key = TRAFFIC_TOTAL_SEND_KEY_FORMAT % (battle_type, )
    my_redis.delete(traffic_recv_key)
    my_redis.delete(traffic_send_key)
    my_redis.srem(TRAFFIC_TYPES, battle_type)


def _saveTrafficData(battle_type, update_minutes=120):
    filename = f'traffic-{battle_type}.json'
    if os.path.exists(filename):
        last_modified_time = datetime.fromtimestamp(os.path.getmtime(filename))
        time_difference = datetime.now() - last_modified_time
        if time_difference <= timedelta(minutes=update_minutes):
            return
    data = json.dumps(getTrafficData(battle_type))
    with open(filename, 'w+') as f:
        f.write(data)
