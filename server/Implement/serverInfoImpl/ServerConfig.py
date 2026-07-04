from dataclasses import dataclass, field


class ServerStatus(object):
    SERVER_CLOSED = '服务器未响应/已关闭'
    SERVER_RUNNING = '服务器运行中'
    SERVER_CLOSING = '服务器关闭中'
    SERVER_RESTARTING = '服务器重启中'
    SERVER_ERROR = '服务器有错误'


@dataclass
class ServerConfig(object):
    # 这部分为配置中应该提供的
    serverName: str = ''
    serverIp: str = None
    serverRestartSchedule: list = field(default_factory=list)
    accessLog: bool = False
    accessDelete: bool = False
    isBattleServer: bool = False  # 是否是battleServer
    needExternalUrl: bool = True  # 是否需要展示对外服务地址
    targetGameServerIp: str = None  # battleServer连接到的战斗服ip
    serverType: str = '999_others'  # 在界面上归类的类别


@dataclass
class ServerRuntimeInfo:
    serverStatus: ServerStatus = ServerStatus.SERVER_CLOSED
    # lastRestartTs: float = 0
    # serverStartTime: datetime = None
    serverDetailInfo: dict = field(default_factory=dict)
    externalUrls: dict = field(default_factory=dict)


dlxServer = ServerConfig()
dlxServer.serverName = 'dlxServer'
dlxServer.serverIp = '172.28.205.44'
dlxServer.serverRestartSchedule = [
    {'day': '*', 'hour': '6', 'minute': '30'},
    {'day': '*', 'hour': '18', 'minute': '30'},
    {'day': '*', 'hour': '21', 'minute': '25'},
]
dlxServer.accessLog = True
dlxServer.accessDelete = True
dlxServer.isBattleServer = False


dlxBattleServer = ServerConfig()
dlxBattleServer.serverName = 'dlxBattleServer'
dlxBattleServer.serverIp = '172.28.205.44'
dlxBattleServer.serverRestartSchedule = [
    # {'day': '*', 'hour': '6', 'minute': '02'},
    # {'day': '*', 'hour': '18', 'minute': '30'},
    # {'day': '*', 'hour': '22', 'minute': '00'},
]
dlxBattleServer.accessLog = True
dlxBattleServer.isBattleServer = True
dlxBattleServer.needExternalUrl = False
dlxBattleServer.targetGameServerIp = '172.28.205.44'

dlxBattleServerCopy = ServerConfig()
dlxBattleServerCopy.serverName = 'dlxBattleServerCopy'
dlxBattleServerCopy.serverIp = '172.28.205.44'
dlxBattleServerCopy.serverRestartSchedule = [
    # {'day': '*', 'hour': '6', 'minute': '02'},
    # {'day': '*', 'hour': '18', 'minute': '30'},
    # {'day': '*', 'hour': '22', 'minute': '00'},
]
dlxBattleServer.accessLog = True
dlxBattleServerCopy.isBattleServer = True
dlxBattleServerCopy.needExternalUrl = False
dlxBattleServerCopy.targetGameServerIp = '172.28.205.44'

c1shenhai = ServerConfig()
c1shenhai.serverName = 'c1公共服深海'
c1shenhai.serverIp = '172.28.193.12'
c1shenhai.serverRestartSchedule = [
]
c1shenhai.accessLog = True
c1shenhai.accessDelete = True
c1shenhai.serverType = '2_shenhai'


c1tianshi = ServerConfig()
c1tianshi.serverName = 'c1公共服甜食'
c1tianshi.serverIp = '172.28.195.150'
c1tianshi.serverRestartSchedule = [
    {'day': '*', 'hour': '6', 'minute': '30'},
    {'day': '*', 'hour': '18', 'minute': '30'},
    # {'day': '*', 'hour': '22', 'minute': '00'},
]
c1tianshi.accessLog = True
c1tianshi.accessDelete = True
c1tianshi.serverType = '1_tianshi'


bsServer = ServerConfig()
bsServer.serverName = '同步服'
bsServer.serverIp = '172.28.204.125'
bsServer.serverRestartSchedule = [
    {'day': '*', 'hour': '9', 'minute': '30'},
    {'day': '*', 'hour': '18', 'minute': '30'},
    {'day': '*', 'hour': '22', 'minute': '00'},
]
bsServer.accessLog = True
bsServer.accessDelete = False
bsServer.needExternalUrl = False
c1tianshi.serverType = '3_branch'


qaServer = ServerConfig()
qaServer.serverName = 'qa测试服'
qaServer.serverIp = '172.28.209.46'
qaServer.serverRestartSchedule = [
    # {'day': '*', 'hour': '9', 'minute': '30'},
    # {'day': '*', 'hour': '18', 'minute': '30'},
    # {'day': '*', 'hour': '22', 'minute': '00'},
]
qaServer.accessLog = True
qaServer.accessDelete = True


BattleServer = ServerConfig()
BattleServer.serverName = '甜食战斗服'
BattleServer.serverIp = '172.28.209.46'
BattleServer.serverRestartSchedule = [
    # {'day': '*', 'hour': '6', 'minute': '35'},
    # {'day': '*', 'hour': '18', 'minute': '35'},
    # {'day': '*', 'hour': '22', 'minute': '05'},
]
BattleServer.accessLog = True
BattleServer.accessDelete = False
BattleServer.isBattleServer = True
BattleServer.needExternalUrl = False
BattleServer.targetGameServerIp = '172.28.195.150'
BattleServer.serverType = '1_tianshi'

shBattleServer = ServerConfig()
shBattleServer.serverName = '深海战斗服'
shBattleServer.serverIp = '172.28.205.99'
shBattleServer.serverRestartSchedule = [
    # {'day': '*', 'hour': '6', 'minute': '35'},
    # {'day': '*', 'hour': '18', 'minute': '35'},
    # {'day': '*', 'hour': '22', 'minute': '05'},
]
shBattleServer.accessLog = True
shBattleServer.accessDelete = False
shBattleServer.isBattleServer = True
shBattleServer.needExternalUrl = False
shBattleServer.targetGameServerIp = '172.28.193.12'
shBattleServer.serverType = '2_shenhai'

branchBattleServer = ServerConfig()
branchBattleServer.serverName = '同步服战斗服'
branchBattleServer.serverIp = '172.28.200.60'
branchBattleServer.serverRestartSchedule = [
    # {'day': '*', 'hour': '6', 'minute': '35'},
    # {'day': '*', 'hour': '18', 'minute': '35'},
    # {'day': '*', 'hour': '22', 'minute': '05'},
]
branchBattleServer.accessLog = True
branchBattleServer.accessDelete = False
branchBattleServer.isBattleServer = True
branchBattleServer.needExternalUrl = False
branchBattleServer.targetGameServerIp = '172.28.204.125'
branchBattleServer.serverType = '3_branch'

c1bvt = ServerConfig()
c1bvt.serverName = 'c1_bvt_测试服'
c1bvt.serverIp = '172.28.209.44'
c1bvt.serverRestartSchedule = [
    {'day': '*', 'hour': '8', 'minute': '00'},
    {'day': '*', 'hour': '18', 'minute': '30'},
    {'day': '*', 'hour': '22', 'minute': '00'},
]
c1bvt.accessLog = True
c1bvt.accessDelete = True


# serverConfigs = [dlxServer, c1tianshi, dlxBattleServer, dlxBattleServerCopy]
serverConfigs = [c1shenhai, c1tianshi, BattleServer, shBattleServer, qaServer, c1bvt, bsServer]
# serverConfigs = [c1shenhai, c1tianshi, shBattleServer, qaServer, c1bvt, bsServer]
