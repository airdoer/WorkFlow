# builtin
from Implement.gameServerImpl.GameServerMgr import GameServerMgr
from appImp import app

# 3rd ext
from flask import request, jsonify

# int
import config
from ._restartCommon import addRestartRoute


# region init
gameServerMgr = GameServerMgr()
# endregion


# region restart
if 'restart' in config.GameServerComponents:
    addRestartRoute(app, gameServerMgr, '')
# endregion

# region deleteAccount
if 'deleteAccount' in config.GameServerComponents:
    @app.route('/deleteAccount', methods=['POST'])
    def doDeleteAccount():
        deleteName = request.json.get('nickName', '')
        app.logger.info(f'delete account: {deleteName}')
        gameServerMgr.deleteAccount(deleteName)
        return jsonify({"message": "成功"})
# endregion
