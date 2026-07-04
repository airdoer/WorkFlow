import functools
import json
import logging
import typing
import gevent
import requests
from dataclasses import asdict

import config
from managers.timeMgr import TimeMgr
from .ServerConfig import ServerStatus, ServerRuntimeInfo

if typing.TYPE_CHECKING:
    from .ServerConfig import ServerConfig
    clientInfoType = typing.Union[ServerConfig, ServerRuntimeInfo]

requestsTimeout = config.InfoManagerRequestsTimeout


def ClientCall(needRunning=True, needNotRestarting=True):
    # 可能由客户端调用过来的需要由这个装饰
    def deco(func):
        @functools.wraps(func)
        def wrap(self: "Server", *args, **kwargs):
            if needNotRestarting and self.inRestarting:
                self.logger.info(f"inRestarting, cannot invoke {func.__name__}")
                return
            if needRunning and self.runtimeInfo.serverStatus != ServerStatus.SERVER_RUNNING:
                self.logger.info(f"not running, cannot invoke {func.__name__}")
                return
            return func(self, *args, **kwargs)
        return wrap
    return deco


class LoggerWithInfo:
    def __init__(self, entity):
        self.entity = entity  # 不用考虑循环引用

    def info(self, *message):
        logging.info(f"{self.entity.logHeader} {message[0]}", *message[1:])


# TODO: 整理一下几个地方response的处理 和 try catch
class Server:
    def __init__(self, serverConfig: "ServerConfig"):
        self.config = serverConfig
        self.runtimeInfo = ServerRuntimeInfo()

        self.logHeader = f"{self.config.serverName}"
        self.logger = LoggerWithInfo(self)

        self._inRestarting = False
        self._restartLockTime = 80  # 设置进入重启状态后 onrequestFail在此时间段内就不会修改服务器为已关闭了
        self._restartFirstRefreshInterval = 20  # 重启状态中 首次刷新的时间 （过早时游戏服http还没有关闭）
        self._restartRefreshInterval = 10  # 重启状态中 刷新时间的间隔

        # self.initRefreshInfo()
        # if config.initCronRestart:
        #     self.initRestartConfig()

    # init
    @staticmethod
    def InitFromConfig(serverConfig: "ServerConfig"):
        if serverConfig.isBattleServer:
            return BattleServer(serverConfig)
        else:
            return GameServer(serverConfig)

    def initRestartConfig(self):
        idx = 0
        for cron_info in self.config.serverRestartSchedule:
            idx += 1
            restartFunc = functools.partial(self.requestRestart, 'cronTab', None)
            TimeMgr.add_schedule_cron(cron_info, restartFunc, f'{self.config.serverName}_cron{idx}_restart')

    def initRefreshInfo(self):
        interval_info = {'minute': config.InfoManagerRefreshInterval}
        # 延迟一会再获取 如果一个flask又是infoManager又是bsManger的话 可能获取信息接口还没初始化好
        TimeMgr.add_schedule_once(5, self._refreshRuntimeInfo, f"{self.config.serverName}_onStart_requestInfo")
        TimeMgr.add_schedule_once(5, self._refreshExtraInfo, f"{self.config.serverName}_onStart_requestExtraInfo")
        TimeMgr.add_schedule_interval(interval_info, self._cronRefreshRuntimeInfo, f'{self.config.serverName}_interval_requestInfo')

    # public
    def getToClientInfo(self) -> "clientInfoType":
        ret = asdict(self.config)
        ret.update(asdict(self.runtimeInfo))
        return ret

    def cancelAllTimer(self):
        pass

    @ClientCall(needRunning=False)
    def requestRefreshInfo(self):
        self.logger.info("client request refresh")
        self._refreshRuntimeInfo()
        self._refreshExtraInfo()
        return self.getToClientInfo()

    @ClientCall(needRunning=False)
    def requestRestart(self, remoteIp, targetSvnVersion):
        if self.inRestarting:
            logging.info(f"{self.config.serverName} already in restarting procedure")
            return
        self.inRestarting = True

        requestUrl = self._getRequestRestartUrl()
        requestJson = {"seconds": 0}
        if remoteIp is not None:
            requestJson['remoteIp'] = remoteIp
        if targetSvnVersion is not None:
            requestJson['target_svn_version'] = targetSvnVersion
        response = requests.post(requestUrl, json=requestJson, timeout=requestsTimeout)
        if response.status_code == 200:
            return True, response.text
        else:
            return False, response.text

    @ClientCall()
    def requestDeleteAccount(self, fromIp, nickname):
        raise NotImplementedError

    # private
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
            TimeMgr.add_schedule_once(self._restartLockTime, self._resetInRestarting, f"{self.config.serverName}_restartingLock")

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
            self._refreshRuntimeInfo()
            self._refreshExtraInfo()  # 重启后挂掉了就刷新不到了
            TimeMgr.add_schedule_once(interval, _requestRefresh, f"{self.config.serverName}_afterRestart_requestInfo_{retryTime}")

        # 第一次延时要长一点 httpService可能还没关闭
        TimeMgr.add_schedule_once(self._restartFirstRefreshInterval, _requestRefresh,
                                  f"{self.config.serverName}_afterRestart_requestInfo_{retryTime}")

    def _cronRefreshRuntimeInfo(self):
        # 常规的定时刷新  重启期间这个刷新不执行 由重启内部的定时器来刷新
        if self.inRestarting:
            self.logger.info("[restarting] in restarting, skip common cron refresh")
            return
        self._refreshRuntimeInfo()

    def _refreshRuntimeInfo(self):
        # 对游戏服 向gameServer 8088端口请求;  对bs 向flask 5000端口请求
        requestUrl = self._getRequestInfoUrl()
        try:
            response = requests.get(requestUrl, json={"level": 'common'}, timeout=requestsTimeout)
            if response.status_code == 200:
                requestedInfo = json.loads(response.text)['msg']
                self._onRequestInfoResponse(requestedInfo)
            else:
                self._onRequestFail()
        except Exception as e:
            logging.info(f"request server info error {requestUrl} {e}")
            self._onRequestFail()

    def _refreshExtraInfo(self):
        #  这个只在启动时、重启后取一次吧
        # 对server类是externalUrl  对bs是svn版本
        if self.config.needExternalUrl:
            requestUrl = self._getRequestInfoExternalUrlUrl()
            try:
                response = requests.get(requestUrl, timeout=requestsTimeout)
                requestedInfo = json.loads(response.text)['msg']
                self.runtimeInfo.externalUrls = requestedInfo
            except Exception:
                pass

    # virtual
    def _getRequestInfoUrl(self):
        raise NotImplementedError

    def _getRequestInfoExternalUrlUrl(self):
        raise NotImplementedError

    def _getRequestRestartUrl(self):
        raise NotImplementedError

    def _onRequestFail(self):
        if self.inRestarting:
            return
        self.runtimeInfo.serverStatus = ServerStatus.SERVER_CLOSED
        self.runtimeInfo.serverDetailInfo.clear()

    def _onRequestInfoResponse(self, requestedInfo):
        self.runtimeInfo.serverStatus = ServerStatus.SERVER_RUNNING
        self.runtimeInfo.serverDetailInfo.update(requestedInfo)


class GameServer(Server):
    def __init__(self, serverConfig: "ServerConfig"):
        super(GameServer, self).__init__(serverConfig)

    # override
    @ClientCall()
    def requestDeleteAccount(self, fromIp, nickname):  # override
        if not self.config.accessDelete:
            return

        response = requests.post(f'http://{self.config.serverIp}:5000/deleteAccount', json={"nickName": nickname}, timeout=requestsTimeout)
        if response.status_code == 200:
            return True, response.text
        else:
            return False, response.text

    def _getRequestInfoUrl(self):  # override
        return f"http://{self.config.serverIp}:8088/info"

    def _getRequestRestartUrl(self):  # override
        return f"http://{self.config.serverIp}:5000/restart"

    def _getRequestInfoExternalUrlUrl(self):  # override
        return f"http://{self.config.serverIp}:8088/outServerInfo"


class BattleServer(Server):
    # TODO: 可能是多台机器上的bs对应一个game，有些请求逻辑不该这么写
    def __init__(self, serverConfig: "ServerConfig"):
        super(BattleServer, self).__init__(serverConfig)
        self._restartLockTime = 15
        self._restartFirstRefreshInterval = 5
        self._restartRefreshInterval = 5
        self.runtimeInfo.serverDetailInfo['targetGameServerIp'] = self.config.targetGameServerIp

    @ClientCall(needRunning=False)
    def requestBattleServerStatistic(self, fromIp):
        # 由flask提供的processNum, detailInfo + 由游戏服提供的status history
        ret = {"gameServerInfo": {}, "battleFlask": {}}

        def requestBattleFlask():
            response = requests.get(f'http://{self.config.serverIp}:5000/getBattleServerInfoRecords', timeout=requestsTimeout)
            ret["battleFlask"] = response.json()

        def requestGame():
            response = requests.get(f'http://{self.config.targetGameServerIp}:8088/getBattleServerStatusHistory', timeout=requestsTimeout)
            ret["gameServerInfo"] = response.json()

        funcList = [requestBattleFlask, requestGame]
        gevent.joinall([gevent.spawn(func) for func in funcList])
        return ret

    # override
    def _getRequestInfoUrl(self):  # override
        return f'http://{self.config.targetGameServerIp}:8088/getBattleServerStatus'

    def _onRequestInfoResponse(self, requestedInfo):  # override
        idleNum = 0
        totalNum = len(requestedInfo)
        for processName, status in requestedInfo.items():
            if status == 0:
                idleNum += 1
        if totalNum == 0:
            self._onRequestFail()
            return
        super(BattleServer, self)._onRequestInfoResponse(requestedInfo)
        self.runtimeInfo.serverDetailInfo['idleProcessNum'] = idleNum
        self.runtimeInfo.serverDetailInfo['processNum'] = totalNum

    def _getRequestRestartUrl(self):  # override
        return f"http://{self.config.serverIp}:5000/battleServer_restart"

    def _refreshExtraInfo(self):
        #  这个只在启动时、重启后取一次吧
        requestUrl = f"http://{self.config.serverIp}:5000/getVersionInfo"
        try:
            response = requests.get(requestUrl, timeout=requestsTimeout)
            requestedInfo = json.loads(response.text)['msg']
            self.runtimeInfo.serverDetailInfo.update(requestedInfo)
        except Exception:
            pass
