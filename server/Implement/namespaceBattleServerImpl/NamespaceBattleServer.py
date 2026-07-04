import copy
import logging
import os
import subprocess
import typing
import weakref
from dataclasses import asdict

import config
from managers.timeMgr import TimeMgr
from .NamespaceBsConfig import ServerRuntimeInfo, ServerConfig, ServerStatus

if typing.TYPE_CHECKING:
    clientInfoType = typing.Union[ServerConfig, ServerRuntimeInfo]
    from .NamespaceBattleServerMgr import NamespaceBattleServerMgr

fileFolder = os.path.dirname(os.path.abspath(__file__))
SHELL_PATH = fileFolder + '/shell'


class LoggerWithInfo:
    def __init__(self, entity: "NamespaceBattleServer"):
        self.entity = weakref.ref(entity)

    def info(self, *message):
        logging.info(f"{self.entity().logHeader} {message[0]}", *message[1:])


class NamespaceBattleServer:
    def __init__(self, mgr: "NamespaceBattleServerMgr", serverConfig: "ServerConfig"):
        self.config = serverConfig
        self.runtimeInfo = ServerRuntimeInfo()
        self.mgr = mgr

        self.logHeader = f"{self.config.Namespace}"
        self.logger = LoggerWithInfo(self)

        self._inRestarting = False
        self._restartLockTime = 60  # 设置进入重启状态后 onrequestFail在此时间段内就不会修改服务器为已关闭了
        self._restartFirstRefreshInterval = 10  # 重启状态中 首次刷新的时间
        self._restartRefreshInterval = 10  # 重启状态中 刷新时间的间隔

        interval_info = {'minute': config.InfoManagerRefreshInterval}
        TimeMgr.add_schedule_interval(interval_info, self._cronRefreshRuntimeInfo, f'{self.config.Namespace}_interval_requestInfo')

    # init
    @staticmethod
    def CheckServerConfig(serverConfig: "ServerConfig"):
        return serverConfig.Namespace.isalnum() \
            and (isinstance(serverConfig.SvnVersion, int) or serverConfig.SvnVersion.isnumeric())

    @staticmethod
    def InitFromConfig(mgr, serverConfig: "ServerConfig"):
        if not NamespaceBattleServer.CheckServerConfig(serverConfig):
            raise RuntimeError(f"run server config {serverConfig = }")
        return NamespaceBattleServer(mgr, serverConfig)

    def _getExternalPort(self):
        return config.Namespace_ExternalPortRange[0] + int(self.config.index)

    def checkAlive(self):
        cmd = f"ps -aux | grep {self.config.Namespace}_battle_server_1 | grep -v grep"
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        stdout, _ = process.communicate()
        output_lines = stdout.decode().split('\n')
        self.logger.info(f"checkAlive, {output_lines = }")
        if output_lines[0]:
            self.runtimeInfo.serverStatus = ServerStatus.SERVER_RUNNING
        else:
            if not self.inRestarting:
                self.runtimeInfo.serverStatus = ServerStatus.SERVER_CLOSED

    # public
    def getToClientInfo(self) -> "clientInfoType":
        ret = asdict(self.config)
        ret.update(asdict(self.runtimeInfo))
        return ret

    def deleteAndRestart(self, oldName):
        deleteScript = f"cd {SHELL_PATH} && bash namespace_delete.sh {config.NameSpace_RootPath} {oldName}"
        externalPort = self._getExternalPort()
        initParams = f"{config.NameSpace_RootPath} {self.config.SvnVersion} {self.config.Namespace} {self.config.TargetAddress} {externalPort} {True} {self.config.index}"  # noqa
        reInitScript = f"cd {SHELL_PATH} && bash namespace_init.sh {initParams}"
        deleteAndRestartScript = deleteScript + " && " + reInitScript
        self.mgr.runShellCmd(deleteAndRestartScript)

    def startProcess(self, needReSvnExport=False):
        if self.inRestarting:
            logging.info(f"{self.config.Namespace} already in restarting procedure")
            return
        self.inRestarting = True

        externalPort = self._getExternalPort()
        initParams = f"{config.NameSpace_RootPath} {self.config.SvnVersion} {self.config.Namespace} {self.config.TargetAddress} {externalPort} {needReSvnExport} {self.config.index}"  # noqa
        initScript = f"cd {SHELL_PATH} && bash namespace_init.sh {initParams}"
        self.mgr.runShellCmd(initScript)
        self.runtimeInfo.serverStatus = ServerStatus.SERVER_RESTARTING
        TimeMgr.add_schedule_once(self._restartLockTime, self._resetInRestarting, f"{self.config.Namespace}_restartingLock")
        return self.getToClientInfo()

    def updateAndRestart(self, fieldName, fieldValue):
        if self.inRestarting:
            logging.info(f"{self.config.Namespace} already in restarting procedure, try changeNamespace")
            return 'in restarting'
        if fieldName in ('index', ):
            logging.info(f"{self.config.Namespace} can not change {fieldName}")
            return 'forbid'

        newConfig = copy.deepcopy(self.config)
        setattr(newConfig, fieldName, fieldValue)
        if not NamespaceBattleServer.CheckServerConfig(newConfig):
            raise RuntimeError(f"run server config {newConfig = }")
        if fieldName == 'Namespace':
            oldName = self.config.Namespace
            self.config = newConfig
            self.deleteAndRestart(oldName)
            return self.getToClientInfo()

        if fieldName in ('SvnVersion'):
            needReSvnExport = True
        else:
            needReSvnExport = False

        self.config = newConfig
        self.startProcess(needReSvnExport=needReSvnExport)
        return self.getToClientInfo()

    def refreshInfo(self):
        if self.inRestarting:
            return self.getToClientInfo()
        self.checkAlive()
        return self.getToClientInfo()

    # restart, refresh
    @property
    def inRestarting(self):
        return self._inRestarting

    @inRestarting.setter
    def inRestarting(self, value):
        self._inRestarting = value
        if value:
            self.logger.info("[restarting] start restarting procedure")
            self.runtimeInfo.serverStatus = ServerStatus.SERVER_RESTARTING
            self.runtimeInfo.serverDetailInfo.clear()
            self._delayRequestStartInfoForRestart()
            TimeMgr.add_schedule_once(self._restartLockTime, self._resetInRestarting, f"{self.config.Namespace}_restartingLock")

    def _resetInRestarting(self):
        self.logger.info("[restarting] end restarting procedure")
        self.inRestarting = False

    def _delayRequestStartInfoForRestart(self):
        # 重启状态中 持续请求刷新信息
        interval = self._restartRefreshInterval
        retryTime = 0

        def _requestRefresh():
            nonlocal retryTime
            retryTime += 1
            self.logger.info(f"[restarting] cron refresh info, {self.inRestarting = } {self.runtimeInfo.serverStatus} {retryTime = }")
            if not self.inRestarting:
                return
            if self.runtimeInfo.serverStatus == ServerStatus.SERVER_RUNNING:
                self.inRestarting = False
                return
            self.checkAlive()
            TimeMgr.add_schedule_once(interval, _requestRefresh, f"{self.config.Namespace}_afterRestart_requestInfo_{retryTime}")

        # 第一次延时要长一点 httpService可能还没关闭
        TimeMgr.add_schedule_once(self._restartFirstRefreshInterval, _requestRefresh,
                                  f"{self.config.Namespace}_afterRestart_requestInfo_{retryTime}")

    def _cronRefreshRuntimeInfo(self):
        # 常规的定时刷新  重启期间这个刷新不执行 由重启内部的定时器来刷新
        if self.inRestarting:
            self.logger.info("[restarting] in restarting, skip common cron refresh")
            return
        self.checkAlive()
