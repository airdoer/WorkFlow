import redis   # 导入redis 模块
from mockData import mock_data_game

pool = redis.ConnectionPool(host='192.168.195.128', port=6379, decode_responses=True, password="redis568178400")
myRedis = redis.Redis(connection_pool=pool)
# myRedis.set('k1', 'vv1')
# print(myRedis['k1'])
# print(myRedis.get('k1'))  # 取出键 name 对应的值
# print(type(myRedis.get('k1')))  # 查看类型

# mydict = {"k1" : "v1", "k2" : "v2"}
# print(mydict)
# print("----------------------------------")
#
# dicts = {"dict1" : {'k1' : 'v1', 'k2' : 'v2', 'k3' : 'v3'},
#          "dict2" : {'kk1' : 'vv1', 'kk2': 'vv2', 'kk3' : 'vv3'}}
# print(dicts)
# print(dicts['dict1']["k1"])
# print(type(dicts['dict1']))
#
# print("------------------------")
# for item in dicts:
#     print(item)
#     print(type(item))
#
#
# print("------------------------")
# myRedis.hset("hash1", "k1", "v1")


# print(mockData)

for gameId in mock_data_game:
    print(mock_data_game[gameId])
    myRedis.hmset(gameId, mock_data_game[gameId])

print("-------------------")
print(myRedis.hget("game1", "player"))

print("--------------------")
print(myRedis.hgetall("game1"))
print(type(myRedis.hgetall("game1")))

print("--------------------------")
print(myRedis.keys("game*"))
print(type(myRedis.keys("game*")))
