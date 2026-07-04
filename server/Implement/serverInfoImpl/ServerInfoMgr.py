# builtin
import functools
import logging
import typing

if typing.TYPE_CHECKING:
    from .Server import Server, BattleServer, GameServer
    ServerType = typing.Union[Server, BattleServer, GameServer]


clientRequestNameLimit = []  # 客户端能用方法名直接请求到的列表


def ClientCanRequest(validateServerName=True):
    # validateServerName为True时，适用于serverName为第二个参数的 检查其是否合法
    def deco(func):
        clientRequestNameLimit.append(func.__name__)
        if not validateServerName:
            return func

        @functools.wraps(func)
        def wrap(self: "ServerInfoManager", serverName, *args, **kwargs):
            if serverName not in self.serverNameToServer:
                logging.info(f"{serverName} not in serverInfos, cannot invoke {func.__name__}")
                return
            return func(self, serverName, *args, **kwargs)
        return wrap

    return deco


class ServerInfoManager:
    def __init__(self):
        self.servers = []
        self.serverNameToServer = {}
        self.initServerInfo()

# region serverInfoManager
    def initServerInfo(self):
        from .ServerConfig import serverConfigs
        from .Server import Server
        # 定时刷新之类的由每个server对象自己做
        self.servers: list["ServerType"] = [Server.InitFromConfig(conf) for conf in serverConfigs]
        self.serverNameToServer: dict[str, "ServerType"] = {server.config.serverName: server for server in self.servers}

    def getServerInfo(self):
        serverInfos = [server.getToClientInfo() for server in self.servers]
        ret = {}  # type -> [ServerInfos]
        for serverInfo in serverInfos:
            ret.setdefault(serverInfo['serverType'], []).append(serverInfo)
        return ret

    @ClientCanRequest(validateServerName=False)
    def requestRefreshAllInfos(self):
        import gevent
        for server in self.servers:
            gevent.spawn(server.requestRefreshInfo)

    @ClientCanRequest(validateServerName=False)
    def requestAllBattleServerName(self):
        ret = []
        for server in self.servers:
            if server.config.isBattleServer:
                ret.append(server.config.serverName)
        return ret

    @ClientCanRequest()
    def requestRefreshInfo(self, serverName):
        server = self.serverNameToServer[serverName]
        return server.requestRefreshInfo()

    # TODO: requests链接的请求状态之类的想办法回传回去
    @ClientCanRequest()
    def requestRestart(self, serverName, fromIp=None, targetSvnVersion=None):
        server = self.serverNameToServer[serverName]
        return server.requestRestart(fromIp, targetSvnVersion)

    @ClientCanRequest()
    def requestDeleteAccount(self, serverName, nickName, fromIp=None):
        server = self.serverNameToServer[serverName]
        if server.config.isBattleServer:
            logging.info(f"{serverName} is battleServer, cannot delete account")
            return
        return server.requestDeleteAccount(fromIp, nickName)

    @ClientCanRequest()
    def requestBattleServerStatistic(self, serverName, fromIp=None):
        server = self.serverNameToServer[serverName]
        if not server.config.isBattleServer:
            logging.info(f"{serverName} is battleServer, cannot delete account")
            return
        return server.requestBattleServerStatistic(fromIp)
# endregion
