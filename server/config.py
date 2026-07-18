import os
host = os.environ.get('work_flow_host', "0.0.0.0")
flask_port = int(os.environ.get('work_flow_port', 16666))

# 填写router目录下的文件名 代表需要引入的接口列表
if 'ROUTER_LIST' in os.environ:
    routerListStr = os.environ.get('ROUTER_LIST')[1:]
    routerList = routerListStr.split(',')
else:
    routerList = ['battle', 'battleExternal', 'heatmap', 'xlsx', 'gameServerRoute', 'battleServerRoute', 'serverInfoRoute', 'hotfixMongoRoute']
    routerList = ['auth', 'WorkFlow']

print('--- use router list: ', routerList)
enableMonkeyPatch = True

# Redis
redis_host = "my_redis"
redis_port = 6379
password = "redispwd"
cluster = False

# mongo
mongo_host = "my_mongo"
mongo_port = 27017
mongo_db = "work_flow"
mongo_user = "admin"
mongo_password = "mongopwd"

# telnet console
TELNET_IP = "0.0.0.0"
TELNET_PORT = 6666

# MySQL
HOSTNAME = "my_mysql"
PORT = 3307
USERNAME = "root"
PASSWORD = "c1pwd"
DATABASE = "work_flow"

CUR_SERVER_NAME = None

P4_WORKSPACE_DIRECTORY = './p4WorkSpace'  # 这个只是为了同步文件，并且不是整个，而是print来下载指定版本的文件
P4_MINI_WORKSPACE_DIRECTORY = './p4MiniWorkSpace'  # miniworkspace是为了commit的

# gameServerManager
GameServerComponents = ['restart', 'deleteAccount']
GameServerShellPath = "/home/c1/Server/shell/linux"
# GameServerShellPath = "/home/dailixing/project/c1/Server/shell/linux"
GameServerDeleteAccountPath = "/home/c1/Server/tools/deleteAccount"
ShellCmdTimeout = 50  # 删号、重启等shell执行的超时时间

# battleServerManger
BattleServerComponents = ['restart', 'processInfo', 'processInfoRecord', 'versionInfo']  # processInfo需要非docker部署
BattleServerShellPath = "/home/c1/BattleServer/shell/battleServer"
# BattleServerShellPath = "/home/dailixing/project/c1/BattleServer/shell/battleServer"
BattleServerProcessPrefix = 'battle_server'
# 参数列表: https://hellowac.github.io/psutil-doc-zh/processes/process_class/cpu_percent.html
BattleServerProcessInfos = [
    "pid",
    "name",
    "cpu_percent",
    "memory_percent",
    "create_time",
]
# 这些也可以用grafana来做
battleStatisticRecordLen = 1000      # 信息记录最大长度
battleStatisticRecordInterval = 10  # 信息记录间隔
battleStatisticRecordItems = [
    "cpu_percent",
    "memory_percent",
]


# serverInfoManager
initCronRestart = True  # 是否开启定时重启
InfoManagerRefreshInterval = 1  # minutes  infomanager刷新信息的频率
InfoManagerRequestsTimeout = 5  # infoManager 发送requests请求给其他进程的最大超时

# namespaceBattleServerManager
NameSpace_RootPath = '/data/c1/NamespaceBattleServer'
Namespace_ExternalPortRange = list(range(40000, 40010 + 1))  # 可用的端口范围 同时决定可用的进程数量上限

# blob config
endpoint_url = "https://bs3-hb1.corp.kuaishou.com"
aws_access_key_id = "17883f3bc7a946e992a20b8235cad665"
aws_secret_access_key = "NjY0MDVmOWMtYzYzYi00YzJhLTg2ZjgtNDA0YjViYWE3ZDgy"
bucket_name = "ksgame-c7-pick-data"
region_name = "hb1"

# auth + kitsso
AUTH_TOKEN_SECRET = os.environ.get('AUTH_TOKEN_SECRET', 'work_flow_auth_secret')
AUTH_TOKEN_EXPIRE_SECONDS = int(os.environ.get('AUTH_TOKEN_EXPIRE_SECONDS', 7 * 24 * 60 * 60))
SSO_URL = os.environ.get('SSO_URL', 'https://sogame-kagura-gateway.corp.kuaishou.com/login')
AUTHEN_GET_URL = os.environ.get('AUTHEN_GET_URL', 'https://sogame-kagura-gateway.corp.kuaishou.com/authen_get?key={key}')
ADMIN_WHITELIST_FILE = os.environ.get('ADMIN_WHITELIST_FILE', './data/auth/admin_whitelist.json')
CHANNEL_MAP_CONFIG_FILE = os.environ.get('CHANNEL_MAP_CONFIG_FILE', './data/mail/channel_map_config.json').strip()

# kdip
KDIP_ENABLE = True
KDIP_ONLINE_DOMAIN = 'https://gamecloud-gmt.corp.kuaishou.com'  # 线上环境
KDIP_DEBUGGING_DOMAIN = 'https://gamecloud-prt.test.gifshow.com'  # 联调环境
KDIP_APP_ID = 'ks697776469461717331'  # c7项目的app-id
KDIP_APP_SECRET = 'KC-VH0uJLxXqEliLwS44Jg'
KDIP_SCOPE = 'game_gm'
KDIP_GRANT_TYPE = 'client_credentials'
KDIP_ACCESS_TOKEN_FILE = './data/kdip/access_token.json'.strip()
KDIP_ACCESS_TOKEN_REFRESH_HOURS = 24
KDIP_REQUEST_TIMEOUT = 10

# game mail dispatch (development-stage guardrails)
MAIL_GAME_SEND_DEV_GUARD_ENABLED = False
MAIL_GAME_SEND_ALLOWED_SERVER_IDS = [
    int(item.strip())
    for item in os.environ.get('MAIL_GAME_SEND_ALLOWED_SERVER_IDS', '114293').split(',')
    if item and item.strip().isdigit()
]
