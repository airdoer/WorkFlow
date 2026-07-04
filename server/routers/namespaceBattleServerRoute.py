# builtin

# 3rd ext
from flask import jsonify
from flask import request

# int
from appImp import app
from Implement.namespaceBattleServerImpl.NamespaceBattleServerMgr import NamespaceBattleServerMgr, clientRequestNameLimit


# from routers.namespaceBattleServerRoute import namespaceBattleServerMgr
# region init
namespaceBattleServerMgr = NamespaceBattleServerMgr()
# endregion


@app.route('/namespaceBs/getAllBsInfos', methods=['GET'])
def nsBsGetBattleServerSvnInfo():
    infos = namespaceBattleServerMgr.getServerInfos()
    return jsonify({"msg": infos})


@app.route('/namespaceBs/addNewBs', methods=['GET'])
def nsBsAddNewOne():
    infos = namespaceBattleServerMgr.addNewServer()
    return jsonify({"msg": infos})


@app.route('/namespaceBs/sendServerRequest', methods=['POST'])
def nsBsSendServerRequest():
    namespace = request.args.get('namespace')
    proxyRoute = request.args.get('proxyRoute')
    if namespace is None or proxyRoute is None or proxyRoute not in clientRequestNameLimit:
        return 'Method not found', 404

    app.logger.info(f'proxy request to {namespace} {proxyRoute}')
    requestArgs = {"namespace": namespace}
    requestArgs.update(request.json)

    # 异常的处理 只在这一层来做吧
    # proxyRoute要做一些限制
    try:
        ret = getattr(namespaceBattleServerMgr, proxyRoute)(**requestArgs)
    except Exception as e:
        app.logger.warning('%s %s unavailable %s', proxyRoute, proxyRoute, e)
        return jsonify({'status': 'noRespond'})

    return jsonify({'status': 'success', 'ret': ret})
