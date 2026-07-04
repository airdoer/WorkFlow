# builtin

# 3rd ext
from flask import jsonify

# int
import config
from ._restartCommon import addRestartRoute
from appImp import app
from Implement.battleServerImpl.BattleServerMgr import BattleServerMgr


# region init
battleServerMgr = BattleServerMgr()
# endregion


# region route
# region restart
if 'restart' in config.BattleServerComponents:
    addRestartRoute(app, battleServerMgr, 'battleServer_')
# endregion


if 'processInfo' in config.BattleServerComponents:
    @app.route('/getBattleServerInfo', methods=['GET'])
    def getBattleServerInfo():
        processInfoList = battleServerMgr.getProcessInfo()
        return jsonify({"msg": {"processNum": len(processInfoList), "detailInfo": processInfoList}})

if 'processInfoRecord' in config.BattleServerComponents:
    @app.route('/getBattleServerInfoRecords', methods=['GET'])
    def getBattleServerInfoRecords():
        records = battleServerMgr.getRecordInfo()
        return jsonify({"record": records, "types": config.battleStatisticRecordItems})

if 'versionInfo' in config.BattleServerComponents:
    @app.route('/getVersionInfo', methods=['GET'])
    def getBattleServerSvnInfo():
        infos = battleServerMgr.getSvnInfo()
        return jsonify({"msg": infos})
