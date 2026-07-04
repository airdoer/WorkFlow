# builtin
import json
import logging
import os
import subprocess
import typing
if typing.TYPE_CHECKING:
    # from typing import TypedDict, Tuple
    pass

# 3rd

# int
import config
from .NamespaceBattleServer import NamespaceBattleServer
from .NamespaceBsConfig import ServerConfig
from Implement.gameServerCommon.GameServerCommon import CommonServerMgr

MAX_SERVER_NUM = len(config.Namespace_ExternalPortRange)

clientRequestNameLimit = []  # 客户端能用方法名直接请求到的列表


def ClientCanRequest():
    # validateServerName为True时，适用于serverName为第二个参数的 检查其是否合法
    def deco(func):
        clientRequestNameLimit.append(func.__name__)
        return func
    return deco


class NamespaceBattleServerMgr(CommonServerMgr):
    def __init__(self, restartScript=None):
        super(NamespaceBattleServerMgr, self).__init__(restartScript)
        # self.servers: list["NamespaceBattleServer"] = []
        self.namespaceToServer: dict[str, "NamespaceBattleServer"] = {}
        self.initDefaultServerInfo()

    # region serverInfoManager
    def initDefaultServerInfo(self):
        # 定时刷新之类的由每个server对象自己做
        fileFolder = os.path.dirname(os.path.abspath(__file__))
        SHELL_PATH = fileFolder + '/shell'
        deleteScript = f"cd {SHELL_PATH} && bash namespace_killAll.sh"
        self.runShellCmd(deleteScript)

        entries = os.listdir(config.NameSpace_RootPath)
        directories = [entry for entry in entries if os.path.isdir(os.path.join(config.NameSpace_RootPath, entry))]

        serverConfigs = []
        for directory in directories:
            confJsonPath = os.path.join(config.NameSpace_RootPath, directory,
                                        "BattleServer/shell/battleServer/namespaceInfo/managerConfig.json")
            with open(confJsonPath, 'r') as file:
                data = json.load(file)

            data.pop("ExternalPort")
            serverConfigs.append(data)

        serverConfigs.sort(key=lambda val: int(val['index']))
        servers = [NamespaceBattleServer.InitFromConfig(self, ServerConfig(**conf)) for conf in serverConfigs]
        # # self.servers = servers
        self.namespaceToServer = {server.config.Namespace: server for server in servers}
        logging.info(f"init server: {list(self.namespaceToServer.keys())}")

    def _getServerConfig(self, namespace, index, svnVersion, targetAddress):
        return ServerConfig(namespace, index, svnVersion, targetAddress)

    # endregion

    def getServerInfos(self):
        serverInfos = [server.getToClientInfo() for server in self.namespaceToServer.values()]
        serverInfos.sort(key=lambda val: int(val['index']))
        ret = {}  # type -> [ServerInfos]
        for serverInfo in serverInfos:
            ret.setdefault(serverInfo['ServerType'], []).append(serverInfo)
        return ret

    def addNewServer(self):
        if len(self.namespaceToServer) + 1 > MAX_SERVER_NUM:
            logging.info("try add new server, server num exceed")
            return "server num exceed"

        curNum = len(self.namespaceToServer)
        index = curNum + 1
        nameSpace = f"newServer{index}"
        svnVersion = self._getNewestSvnVersion()
        targetAddress = "127.0.0.1:10000"

        bs = NamespaceBattleServer.InitFromConfig(self, self._getServerConfig(nameSpace, index, svnVersion, targetAddress))
        # self.servers.append(bs)
        self.namespaceToServer[nameSpace] = bs
        return bs.startProcess(needReSvnExport=True)

    # @ClientCanRequest()
    # def addBattleServer(self, namespace, svnVersion, targetAddress):
    #     if len(self.namespaceToServer) + 1 > MAX_SERVER_NUM:
    #         logging.info(f"try add {namespace}, server num exceed")
    #         return "server num exceed"
    #     if namespace in self.namespaceToServer:
    #         logging.info(f"try add {namespace} already exists")
    #         return "already exist"

    #     logging.info(f"{namespace} not exists, start new one")
    #     bs = NamespaceBattleServer.InitFromConfig(self, self._getServerConfig(namespace, svnVersion, targetAddress))
    #     # self.servers.append(bs)
    #     self.namespaceToServer[namespace] = bs
    #     return bs.startProcess()

    @ClientCanRequest()
    def updateBattleServer(self, namespace, fieldName, fieldValue):
        if namespace not in self.namespaceToServer:
            logging.info(f"try update {namespace} not exists")
            return "namespace not exist"

        bs = self.namespaceToServer[namespace]
        ret = bs.updateAndRestart(fieldName, fieldValue)
        if bs.config.Namespace != namespace:
            self.namespaceToServer.pop(namespace)
            self.namespaceToServer[bs.config.Namespace] = bs
        return ret

    @ClientCanRequest()
    def requestRefreshInfo(self, namespace):
        if namespace not in self.namespaceToServer:
            logging.info(f"try refresh {namespace} not exists")
            return "namespace not exist"

        bs = self.namespaceToServer[namespace]
        return bs.refreshInfo()

    @ClientCanRequest()
    def restartBattleServer(self, namespace):
        if namespace not in self.namespaceToServer:
            logging.info(f"try restart {namespace} not exists")
            return "namespace not exist"

        # if targetSvnVersion is None:
        #     svnVersion = self._getNewestSvnVersion()
        # else:
        #     svnVersion = targetSvnVersion
        bs = self.namespaceToServer[namespace]
        # return bs.updateAndRestart('SvnVersion', svnVersion)
        return bs.startProcess()

    def _getNewestSvnVersion(self):
        SVN_URL = "svn://172.20.6.1/c1/trunk/DedicatedServer/linux-x64"
        cmd = "svn info %s --username c1_packer --password Hzks6666 | grep 'Revision' | awk '{print $2}'" % SVN_URL
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        elif isinstance(cmd, str):
            cmd = cmd
        else:
            raise ValueError("cmd(%s) must be str or list" % (cmd, ))
        print("cmd:", cmd)
        res = subprocess.run(cmd, capture_output=True, check=True, shell=True, text=True)
        return res.stdout.strip('\n')
