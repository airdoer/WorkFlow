import typing
import time
if typing.TYPE_CHECKING:
    from flask import Flask
    from Implement.gameServerCommon.GameServerCommon import CommonServerMgr
    pass

from flask import request, jsonify


def addRestartRoute(app: "Flask", serverMgr: "CommonServerMgr", routePrefix=''):
    @app.route(f'/{routePrefix}restartTime', methods=['GET'], endpoint=f'{routePrefix}restartTime')
    def restartTime(serverMgr):
        # 这个接口目前没用到的
        app.logger.info("{routePrefix} flask getRestartTime {routePrefix}")
        restartSchedules = serverMgr.getRestartSchedule()
        return jsonify({"ret": restartSchedules})

    @app.route(f'/{routePrefix}restart', methods=['POST'], endpoint=f'{routePrefix}doRestart')
    def doRestart():
        client_ip = request.remote_addr

        from datetime import datetime
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")

        data = request.json
        from_ip = data.get("remoteIp", "notKnown")
        target_svn_version = data.get("target_svn_version", None)
        delay = data.get("seconds", 0)

        app.logger.info(
            f"{routePrefix} flask doRestart streamLitIp: {client_ip} fromIp: {from_ip} time: {formatted_time} targetSvnVer:{target_svn_version}")  # noqa
        if delay < 0:
            return jsonify({"message": "重启参数异常"})

        serverMgr.requestRestart(delay, target_svn_version)
        return jsonify({"message": "将在[" + time.strftime('%H:%M:%S', time.localtime(time.time() + delay)) + "]重启服务器"})

    @app.route(f'/{routePrefix}cancelRestart', methods=['POST'], endpoint=f'{routePrefix}doCancelRestart')
    def doCancelRestart():
        # 这个接口目前也没用到
        app.logger.info("{routePrefix} flask doCancelRestart")

        data = request.json
        cancelJobId = data.get("cancelJobId", None)
        serverMgr.cancelRestart(cancelJobId)
        return jsonify({"message": "取消重启成功!"})
