# builtin
from appImp import app

# 3rd ext
from flask import request, jsonify

# int
from Implement.serverInfoImpl.ServerInfoMgr import ServerInfoManager, clientRequestNameLimit

# region init
serverInfoManager = ServerInfoManager()
# endregion


# 就给两类接口  一个获取全量信息  一个提供ip和给定method 让flask发送请求
@app.route('/getAllServerInfos', methods=['GET'])
def getAllServerInfos():
    serversInfo = serverInfoManager.getServerInfo()
    return jsonify({'msg': serversInfo})


@app.route('/getAllBattleServerName', methods=['GET'])
def getAllBattleServerName():
    serversNames = serverInfoManager.requestAllBattleServerName()
    return jsonify({'msg': serversNames})


@app.route('/refreshAllInfos', methods=['POST'])
def refreshAllInfos():
    serverInfoManager.requestRefreshAllInfos()
    return jsonify({'msg': 'success'})


# 网页发过来的重启、删号之类的指令全部由这里转发给其他flask
# 'requestRestart', 'requestDeleteAccount'
@app.route('/sendServerRequest', methods=['POST'])
def sendServerRequest():
    serverName = request.args.get('serverName')
    proxyRoute = request.args.get('proxyRoute')
    if serverName is None or proxyRoute is None or proxyRoute not in clientRequestNameLimit:
        return 'Method not found', 404

    app.logger.info(f'proxy request to {serverName} {proxyRoute}')
    requestArgs = {"serverName": serverName}
    requestArgs.update(request.json)

    # 异常的处理 只在这一层来做吧
    # proxyRoute要做一些限制
    try:
        ret = getattr(serverInfoManager, proxyRoute)(**requestArgs)
    except Exception as e:
        app.logger.warning('%s %s unavailable %s', proxyRoute, proxyRoute, e)
        return jsonify({'status': 'noRespond'})

    return jsonify({'status': 'success', 'ret': ret})

# endregion
