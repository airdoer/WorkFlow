import redis  # 导入redis 模块
import config
from data import C3_AllVectorIDMap
from datetime import datetime

pool = redis.ConnectionPool(host=config.redis_host, port=config.redis_port, decode_responses=True, password=config.password)
my_redis = redis.Redis(connection_pool=pool)

MEMORY_KEY_FORMAT = "C3_{memory}_MemoryStatistic_%s"

CONSIST_KEY = "C3_CONSIST_STATISTIC"

CONSIST_ACC_KEY_0 = "C3_CONSIST_ACC_STATISTIC_0"
CONSIST_ACC_KEY_1 = "C3_CONSIST_ACC_STATISTIC_1"
BATTLE_ACC_KEY = "C3_BATTLE_ACC_STATISTIC"


def addBattleStatistic(player_counts: int, consist_status: bool, start_time: float, game_id: str):
    my_redis.incr(BATTLE_ACC_KEY, 1)
    if player_counts >= 2:
        # 形式如下:
        # score: 1689268660
        # member: 1689268660.0_1
        _map = {f"{game_id}_{int(consist_status)}": start_time}
        my_redis.zadd(CONSIST_KEY, _map)
        if consist_status:
            my_redis.incr(CONSIST_ACC_KEY_1, 1)
        else:
            my_redis.incr(CONSIST_ACC_KEY_0, 1)


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


def clearOverTimeConsistStatistic():
    # 清理两个小时前的consistKey
    early_time = datetime.now().timestamp() - 60 * 60 * 2
    my_redis.zremrangebyscore(CONSIST_KEY, 0, early_time)


def clearConsistStatistic():
    clearOverTimeConsistStatistic()
    my_redis.set(BATTLE_ACC_KEY, 0)
    my_redis.set(CONSIST_ACC_KEY_1, 0)
    my_redis.set(CONSIST_ACC_KEY_0, 0)


def addMemoryData(inputMemoryData):
    battle_type = inputMemoryData.pop("battleType", "all")
    title = inputMemoryData.pop("title", "all")
    gameId = inputMemoryData.pop("gameId", "")

    memory_key = MEMORY_KEY_FORMAT % (battle_type, )

    memory = my_redis.hgetall(memory_key)
    print(f'redisImp memoryData {gameId} {battle_type} {title}')
    memoryData = {}

    for k, v in inputMemoryData.items():
        idx = k.rfind('_')
        k_name = k[:idx]
        default_value = int(k[idx+1:])
        if k_name not in C3_AllVectorIDMap.data:
            # print(f'redisImp Error: [{k_name}]  not in AllVectorIDMap data')
            # continue
            if not memory or f'{k_name}_default' not in memory:
                my_redis.hset(memory_key, f'{k_name}_default', default_value)
                my_redis.hset(memory_key, f'{k_name}_max', v)
                my_redis.hset(memory_key, f'{k_name}_gameId', gameId)
            else:
                if int(float(memory.get(f'{k_name}_default', 0))) != default_value:
                    my_redis.hset(memory_key, f'{k_name}_default', default_value)
                if int(float(memory.get(f'{k_name}_max', 0))) < v:
                    my_redis.hset(memory_key, f'{k_name}_max', v)
                    my_redis.hset(memory_key, f'{k_name}_gameId', gameId)
            continue
        memoryData[f'{k_name}_max'] = v
        memoryData[f'{k_name}_default'] = default_value

    if not memory:
        init_kv = {
            'battle_type': battle_type,
            'title': title,
        }
        for k in C3_AllVectorIDMap.data:
            k_default = f'{k}_default'
            k_max = f'{k}_max'
            k_gameId = f'{k}_gameId'

            if k_default in memoryData:
                init_kv[k_default] = memoryData[k_default]
                init_kv[k_max] = memoryData[k_max]
                init_kv[k_gameId] = gameId
            else:
                init_kv[k_default] = C3_AllVectorIDMap.data[k]
                init_kv[k_max] = 0
                init_kv[k_gameId] = ''
        for k, v in init_kv.items():
            my_redis.hset(memory_key, k, v)
    else:
        for k in C3_AllVectorIDMap.data:
            k_default = f'{k}_default'
            k_max = f'{k}_max'
            k_gameId = f'{k}_gameId'
            if k_default in memoryData and int(memory.get(k_default, 0)) != memoryData[k_default]:
                my_redis.hset(memory_key, k_default, memoryData[k_default])
            if k_max in memoryData and int(memory.get(k_max, 0)) <= memoryData[k_max]:
                my_redis.hset(memory_key, k_max, memoryData[k_max])
                my_redis.hset(memory_key, k_gameId, gameId)


def renderMemoryData(memoryData):
    ret_list = []
    for k in sorted(C3_AllVectorIDMap.data):
        ret_list.append({
            "type": "default",
            "object": k,
            "value": int(float(memoryData.get(f'{k}_default', 0))),
            "gameId": memoryData.get(f'{k}_gameId', 0)
        })
    for k in sorted(C3_AllVectorIDMap.data):
        ret_list.append({
            "type": "max",
            "object": k,
            "value": int(float(memoryData.get(f'{k}_max', 0))),
            "gameId": memoryData.get(f'{k}_gameId', 0)
        })
    return ret_list


def getMemoryData():
    battle_type = "all"
    memory_key = MEMORY_KEY_FORMAT % (battle_type, )
    memory = my_redis.hgetall(memory_key)
    resData = {}
    battleType = [{
        "id": memory.get("battle_type"),
        "title": memory.get("title")
    }]
    resData[memory.get("battle_type")] = renderMemoryData(memory)
    resData["battleType"] = battleType
    return resData


def deleteMemoryData():
    my_redis.delete("C3_{memory}_MemoryStatistic_all")
    return "deleteMemoryData return"
