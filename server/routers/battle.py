# 和游戏服务器 战斗相关的route放这个里 这里只放对内的接口 对外的放battleExternal里

# builtin
import logging
import pickle
from base64 import b64decode
from datetime import datetime, timedelta

# 3rd ext
from flask import render_template, request, jsonify, Response
from sqlalchemy import and_
import io
import csv

# int
from appImp import app
from dbImp import mysqlImp, redisImp
from models.c1.battle import Battle as C1_Battle
from models.c1.player import Player as C1_Player

from exts import db
from httpImp import requestImp

from utility import retCode, const, hotfixUtils, httpUtils
import g

# region init

# endregion


# region route

@app.route("/avReportBattleCheat", methods=["POST"])
def avReportBattleCheat():
    # 排行榜上传信息接口，用于标识某些特殊战斗优先被校验
    data = request.get_json()
    battleId = data.get('battleId')
    cheatOp: int = data.get("cheatOp")
    app.logger.info(f"avReportBattleCheat {battleId=} {cheatOp=}")
    if cheatOp not in const.BattleCheatDescription:
        retData = {"errMsg": f'cheatOp {cheatOp=} not in const.BattleCheatDescription'}
    else:
        ret = mysqlImp.updateCheatStatus(battleId, cheatOp)
        if ret == retCode.CheatStatusRetCode.BattleNotExist:
            # 一般是战斗还没结束，所以延后再上传
            g.timeMgr.add_timer(const.REPORT_CHEAT_DELAY, lambda: mysqlImp.updateCheatStatusRetry(battleId, cheatOp))
            g.timeMgr.add_timer(const.REPORT_CHEAT_DELAY, lambda: redisImp.upCheckBattleId(battleId))
        else:
            # 同时加入到优先校验列表中
            g.timeMgr.add_timer(const.CHEAT_UP_DELAY, lambda: redisImp.upCheckBattleId(battleId))
        retData = {"code": ret}
    app.logger.info(f"avReportBattleCheat {retData} End")
    return jsonify(retData)


@app.route("/rankListBattleInfo", methods=["POST"])
def rankListBattleInfo():
    # 排行榜上传信息接口，用于标识某些特殊战斗优先被校验
    data = request.get_json()
    battleId = data.get('battleId')
    playerId: str = data.get("playerId")
    rankType: str = data.get('rankType')
    rankIndex: int = data.get('rankIndex')
    app.logger.info(f"rankListBattleId {battleId=} {playerId=} {rankType=} {rankIndex=}")
    # 类似于这种结构
    # battleId='724985e6c35a11ef8e0f415dd7f4ee36' playerId='141151762' rankType='official_100600005' rankIndex=212
    rankId = rankType.split('_')[1]
    rankId = int(rankId)
    if rankId in const.AUTO_DEL_RANK_IDS:
        # 属于无限boss的排行榜，存到redis中
        redisImp.addRankRecord(battleId, playerId, rankType)
        # 同时加入到优先校验列表中
        redisImp.upCheckBattleId(battleId)
    ret = mysqlImp.updateCheatStatus(battleId, const.BattleCheatOperation['RankListTop'])
    retData = {"code": ret}
    app.logger.info(f"rankListBattleId {retData} End")
    return jsonify(retData)


@app.route("/getCheckBattleId", methods=["POST"])
def getCheckBattleId():
    # 获取当前需要校验的战斗
    data = request.get_json()
    app.logger.info(f"getCheckBattleId {data=}")

    # ret = mysqlImp.getCheckBattleId(battleId, const.BattleCheatOperation['RankListTop'])
    gameId = redisImp.getCheckBattleId()
    if gameId:
        app.logger.info(f"getCheckBattleId get gameId via redis {gameId}")
        # 说明找到对应battleId了
        mysqlImp.setBattleChecking(gameId)
    else:
        battleIds = mysqlImp.getCheckBattleIds(const.UP_CHEAT_CNT)
        app.logger.info(f"getCheckBattleId get gameIds via mysql {battleIds}")
        if battleIds:
            redisImp.inputCheckBattleIds(battleIds[1:])
            mysqlImp.setBattleChecking(battleIds[0])
            gameId = battleIds[0]
            app.logger.info(f"getCheckBattleId get gameId via mysql {gameId}")
    retData = {"gameId": gameId}
    app.logger.info(f"getCheckBattleId {retData} End")
    return jsonify(retData)


@app.route('/uploadHotfix', methods=['POST'])
def uploadHotfix():
    uploadInfo = pickle.loads(b64decode(request.data))
    uploadType = uploadInfo['uploadType']
    hotfixInfo = uploadInfo['hotfixInfo']
    app.logger.info(f"czx uploadHotfix start {uploadType=}")
    # hotfixInfo形式:
    # {
    #    serverId:
    #   {
    #       # hotfixType属于'client', 'server', 'clientResource'
    #       hotfixType: list [hotfixName, hotfixValue]
    #   }
    # }
    g.hotfixInfo = hotfixInfo
    serverId = list(hotfixInfo.keys())[0]
    resourceHotfixInfo = {}

    for hotfixType, hotfixList in hotfixInfo[serverId].items():
        for hotfixValue in hotfixList:
            hotfixName, hotfixContent = hotfixValue
            if hotfixType == 'server':
                continue
            if hotfixType == 'client':
                continue
            if hotfixType == 'clientResource':
                if hotfixUtils.isClientCsfix(hotfixName):  # csfix
                    if hotfixUtils.isDedicatedServerCsFix(hotfixName):  # dedicated server
                        _hotfixName, resourcePath = hotfixUtils.getClientResourcePath(hotfixName)
                        resourceHotfixInfo[_hotfixName] = [resourcePath, hotfixContent]
                    else:
                        pass
                else:  # 二进制资源
                    # 这里的hotfixName是fullHotfixName
                    # hotfixName: Temp_zht_roofevent2_graphview.bytes;;;Des/Environment/Datas/GraphViewData/Intern_temp/Temp_zht_roofevent2_graphview.bytes的形式  # noqa
                    # _hotfixName: Temp_zht_roofevent2_graphview.bytes
                    # Des/Environment/Datas/GraphViewData/Intern_temp/Temp_zht_roofevent2_graphview.bytes
                    _hotfixName, resourcePath = hotfixUtils.getClientResourcePath(hotfixName)
                    resourceHotfixInfo[_hotfixName] = [resourcePath, hotfixContent]
    g.uploadType = uploadType
    g.resourceHotfixInfo = resourceHotfixInfo
    if uploadType == 'all':
        redisImp.clearHotfix()
        if resourceHotfixInfo:
            redisImp.addHotfix(resourceHotfixInfo)
    else:  # add
        if resourceHotfixInfo:
            redisImp.addHotfix(resourceHotfixInfo)
    return 'uploadHotfix Return'


@app.route('/getHotfix', methods=['GET'])
def getHotfix():
    # 获取单个hotfix
    app.logger.info("czx getHotfix start")
    hotfixName = request.args.get('hotfixName')
    ret = redisImp.getHotfix(hotfixName)
    return ret


@app.route('/syncHotfixList', methods=['POST'])
def syncHotfixList():
    # 客户端上传自己的hotfix列表，检索一下还需要同步的hotfix
    app.logger.info("czx getHotfix start")
    data = request.get_json()
    hotfixList = data.get('hotfixList', [])
    ret = redisImp.syncHotfixList(hotfixList)
    return ret


@app.route('/uploadBattle', methods=['POST'])
def uploadBattle():
    # app.logger.info("czx uploadBattle start")
    uploadInfo = pickle.loads(b64decode(request.data))
    project = uploadInfo['project']

    game_id = uploadInfo['battleId']
    server_name = uploadInfo['serverName']
    version = uploadInfo['version']
    start_time = uploadInfo['startTs']
    duration = uploadInfo.get('duration')
    consist_status: bool = uploadInfo['consistStatus']
    player_counts: int = len(uploadInfo['playerInfos'])
    inconsistent_frame_counts = uploadInfo['inconsistentFrameCounts']
    player_infos = uploadInfo['playerInfos']
    cheat_op = uploadInfo['cheatOp']

    if cheat_op != const.BattleCheatOperation['NoCheat']:
        g.timeMgr.add_timer(const.CHEAT_UP_DELAY, lambda: redisImp.upCheckBattleId(game_id))

    logging.info(
        f'uploadBattle {project=}, {game_id=}, {server_name=}, {version=}, {start_time=}, {duration=}, '
        f'{consist_status=}, {player_counts=}, {inconsistent_frame_counts=}, {player_infos=} {cheat_op=}')

    replay = uploadInfo.get('replay')
    if replay:
        replay_info = pickle.dumps(uploadInfo['replay'])  # bytes type
        uploadInfo['replay'] = replay_info

    curTs = datetime.now().timestamp()
    # logging.info(f'addBattleStatistic {project}, {game_id}, {consist_status} {player_counts}')
    mysqlImp.addBattleData(uploadInfo)
    redisImp.addBattleStatistic(player_counts, consist_status, curTs, game_id, uploadInfo.get('useBattleServer', False))

    # recordFile、battleId、playerId、ts、serverName、version、duration、consist
    # app.logger.info("czx uploadBattle end")
    return 'uploadBattle Return'


@app.route('/uploadRoomInfo', methods=['POST'])
def uploadRoomInfo():
    app.logger.info("lyw uploadRoomInfo start")
    uploadInfo = pickle.loads(b64decode(request.data))
    game_id = uploadInfo['battleId']
    room_id = uploadInfo['roomId']
    frame_id = uploadInfo['frameId']

    logging.info(f'uploadRoomInfo {game_id = }, {room_id = } {frame_id = }')
    mysqlImp.addRoomInfo(uploadInfo)

    app.logger.info("lyw uploadRoomInfo end")
    return 'uploadRoomInfo Return'


@app.route('/getConsistStatistic', methods=['GET'])
def getConsistStatistic():
    app.logger.info("getConsistStatistic")
    retData = redisImp.getConsistStatistic()
    logging.info(f'c1 getConsistStatistic {retData}')
    return jsonify({
        'result': retData
    })


@app.route('/getAutoDelRankRecords', methods=['GET'])
def getAutoDelRankRecords():
    app.logger.info("getAutoDelRankRecords")
    delRankRecords = redisImp.getAutoDelRankRecords()
    # retData:
    # [{
    #     "player": "141151762",
    #     "rankBattleIds": [
    #         "channel_100600005:battleIdString4",
    #         "channel_100600005:battleIdString3",
    #         "official_100600005:battleIdString1",
    #         "channel_100600005:battleIdString5",
    #         "official_100600005:battleIdString2"
    #     ],
    #     "time": 1737647523.029994
    # }]
    for delRankRecord in delRankRecords:
        if 'rankBattleIds' in delRankRecord:
            rankIds = []
            battleIds = []
            for rankBattleId in delRankRecord['rankBattleIds']:
                rankId, battleId = rankBattleId.split(':', 1)
                rankIds.append(rankId)
                battleIds.append(battleId)
            # Update the record
            delRankRecord['rankIds'] = rankIds
            delRankRecord['battleIds'] = battleIds
            delRankRecord.pop('rankBattleIds')
    # 根据time进行排序，最晚的在最前面
    delRankRecords.sort(key=lambda x: x['time'], reverse=True)
    logging.info(f'c1 getAutoDelRankRecords {delRankRecords}')
    return jsonify({
        'result': delRankRecords
    })


@app.route('/gameInfos')
def games_all_info():  # put application's code here
    games = redisImp.get_all_game_data()
    return render_template("index.html", games=games)


@app.route('/edition')
def games_with_edition():
    edition = request.args.get("edition")
    games = redisImp.get_edition_game_data(edition)
    return jsonify({"code": 200, "message": "", "games": games})


@app.route('/user/info', methods=['GET', 'OPTIONS'])
def getUserInfo():
    userInfo = {
        "id": '4291d7da9005377ec9aec4a71ea837f',
        'name': 'KsGamer',
        'username': 'admin',
        'password': '',
        'avatar': '/avatar2.jpg',
        'status': 1,
        'telephone': '',
        'lastLoginIp': '27.154.74.117',
        'lastLoginTime': 1534837621348,
        'creatorId': 'admin',
        'createTime': 1497160610259,
        'merchantCode': 'TLif2btpzg079h15bk',
        'deleted': 0,
        'roleId': 'admin',
        'role': {}
    }
    roleObj = {
        'id': 'admin',
        'name': '管理员',
        'describe': '拥有所有权限',
        'status': 1,
        'creatorId': 'system',
        'createTime': 1497160610259,
        'deleted': 0,
        'permissions': [
            {
                'permissionId': 'dashboard',
                'permissionName': '仪表盘',
                'actions':
                    '[{"action":"add","defaultCheck":false,"describe":"新增"},{"action":"query","defaultCheck":false,"describe":"查询"},{"action":"get","defaultCheck":false,"describe":"详情"},{"action":"update","defaultCheck":false,"describe":"修改"},{"action":"delete","defaultCheck":false,"describe":"删除"}]',  # noqa
                'actionEntitySet': [
                    {
                        'action': 'add',
                        'describe': '新增',
                        'defaultCheck': False
                    },
                    {
                        'action': 'query',
                        'describe': '查询',
                        'defaultCheck': False
                    },
                    {
                        'action': 'get',
                        'describe': '详情',
                        'defaultCheck': False
                    },
                    {
                        'action': 'update',
                        'describe': '修改',
                        'defaultCheck': False
                    },
                    {
                        'action': 'delete',
                        'describe': '删除',
                        'defaultCheck': False
                    }
                ],
                'actionList': [],
                'dataAccess': []
            }
        ]
    }
    userInfo['role'] = roleObj
    return jsonify({
        'result': userInfo,
    })


@app.route('/getCheatStatistic', methods=['GET'])
def getCheatStatistic():
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    _cheatOp = httpUtils.get_arg_as_int(request, 'cheat_op', 0)
    review_server_status = httpUtils.get_arg(request, 'review_server_status', '')
    review_people_status = httpUtils.get_arg(request, 'review_people_status', '')
    battle_type = httpUtils.get_arg(request, 'battle_type', '')
    multi_status = httpUtils.get_arg_as_int(request, 'multi_status', -1)

    proj_battle = C1_Battle
    proj_player = C1_Player
    battle_order = proj_battle.start_time.desc()
    startTime_datetime = datetime.strptime(start_time, const.TIME_FORMAT)
    endTime_datetime = datetime.strptime(end_time, const.TIME_FORMAT)
    app.logger.info(f'czx getCheatStatistic {start_time=}, {end_time=}, {_cheatOp=}, {battle_type=}, {multi_status=}, '
                    f'{review_server_status=}, {review_people_status=}')
    if startTime_datetime >= endTime_datetime:
        return jsonify({'result': '开始时间需要小于结束时间'})
    threshold_datetime = startTime_datetime + timedelta(days=1)  # 第二天 00:00:00
    if endTime_datetime > threshold_datetime:
        return jsonify({'result': '日期超出范围'})
    filterCondition = [
        proj_battle.start_time >= startTime_datetime,  # 设定日期过滤
        proj_battle.end_time < endTime_datetime,  # 设定第二天限制
    ]
    if _cheatOp != 0:
        filterCondition.append(proj_battle.cheat_op == _cheatOp)  # 设定 cheat_op 过滤
    if review_server_status:
        filterCondition.append(proj_battle.review_server_status == review_server_status)
    if review_people_status:
        filterCondition.append(proj_battle.review_people_status == review_people_status)
    if battle_type:
        filterCondition.append(proj_battle.type == battle_type)
    if multi_status == 0:
        filterCondition.append(proj_battle.multi_status == False)  # noqa
    elif multi_status == 1:
        filterCondition.append(proj_battle.multi_status == True)  # noqa

    battles = proj_battle.query.with_entities(proj_battle.game_id, proj_battle.end_time).\
        filter(and_(*filterCondition)).order_by(battle_order).all()
    if not battles:
        return jsonify({'result': '无数据'})
    battle_ids = [battle.game_id for battle in battles]
    battle_end_times = [battle.end_time for battle in battles]
    battle_dict = {battle_id: end_time for battle_id, end_time in zip(battle_ids, battle_end_times)}
    players = proj_player.query.filter(proj_player.battle_id.in_(battle_ids)).\
        with_entities(proj_player.role_id, proj_player.battle_id, proj_player.device_id).all()
    output = io.StringIO()
    csv_writer = csv.writer(output)
    csv_writer.writerow(['role_id', 'game_id', 'device_id', 'battle_end_time', 'cheat_op'])
    for player in players:
        csv_writer.writerow([player.role_id, player.battle_id, player.device_id, battle_dict[player.battle_id], _cheatOp])
    output.seek(0)  # 将游标移动到文件开始
    file_name = f'players-{start_time}-{end_time}-{_cheatOp}.csv'
    return Response(output, mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=' + file_name})


# 迭代为数据库交互
@app.route('/battleList', methods=['GET'])
def getBattleList():
    versionList = [float(x) for x in request.args.getlist('version[]')]
    serverNameList = request.args.getlist('serverName[]')
    pageNo = request.args.get('pageNo')
    pageSize = request.args.get('pageSize')
    project = request.args.get('project')
    playerNames = request.args.get("playerNames")
    playerId: str = request.args.get("playerId")
    gameId: str = request.args.get("gameId")
    serverName = request.args.get("serverName")
    startTime = request.args.get("startTime")
    endTime = request.args.get("endTime")
    consistInfo = request.args.get("consistInfo")
    battleVersion = request.args.get("battleVersion")
    engineVersion = request.args.get("engineVersion")
    patchVersion = request.args.get("patchVersion")
    os = request.args.get("os")
    inconsistOnly = request.args.get("inconsistOnly")
    teamOnly = request.args.get("teamOnly")
    _reviewServerStatus = request.args.get("reviewServerStatus")
    _reviewPeopleStatus = request.args.get("reviewPeopleStatus")
    _cheatOp = request.args.get("cheatOp")
    battleType = request.args.get("battleType")
    multiStatus = int(request.args.get("multiStatus", '-1'))

    app.logger.info(f'battleList args is:  {project=} {playerNames=}, {versionList=}, {serverName=}, {serverNameList=}, '
                    f'{gameId=}, {startTime=}, {endTime=}, {pageNo=}, {pageSize=}, {consistInfo=}, {inconsistOnly=}, {teamOnly=}, '
                    f'{_reviewServerStatus=}, {_reviewPeopleStatus=} {_cheatOp=} {battleType=} {multiStatus=}')

    pageSize = int(pageSize)
    pageNo = int(pageNo)

    proj_battle = C1_Battle
    proj_player = C1_Player

    playerFields = [proj_player.battle_id, proj_player.id]
    allPageCount: int = 0
    filterCondition = []
    validBattleData = []
    needSearch = True

    # 从player表中获取battle_id再在battle中搜索
    # 目前的逻辑是假定playerNames只上传一个而非多个
    playerFilterCondition = [
        # proj_player.start_time > (datetime.now() - timedelta(days=7)),
    ]
    playerQuery = None

    if playerNames:
        playerFilterCondition.append(proj_player.name == playerNames)
    elif playerId:
        if project == "c1" and playerId.isnumeric():
            playerFilterCondition.append(proj_player.role_id == playerId)
        else:
            playerFilterCondition.append(proj_player.player_id == playerId)

    if engineVersion:
        playerFilterCondition.append(proj_player.local_engine_version == engineVersion)
    if patchVersion:
        playerFilterCondition.append(proj_player.local_patch_version == patchVersion)
    if os:
        playerFilterCondition.append(proj_player.os == os)

    if playerFilterCondition:
        playerQuery = db.session.query(*playerFields).filter(and_(*playerFilterCondition)).order_by(proj_player.id.desc())
        allPageCount = playerQuery.count()
        if allPageCount > (pageNo - 1) * pageSize:
            pass
        else:
            needSearch = False

    if needSearch:
        if serverName:
            filterCondition.append(proj_battle.server_name == serverName)
        if startTime:
            startTime_datetime = datetime.strptime(startTime, const.TIME_FORMAT)
            filterCondition.append(proj_battle.start_time > startTime_datetime)
        if endTime:
            endTime_datetime = datetime.strptime(endTime, const.TIME_FORMAT)
            filterCondition.append(proj_battle.end_time < endTime_datetime)
        if consistInfo:
            consistInfo_bool = bool(int(consistInfo))
            filterCondition.append(proj_battle.consist_status == consistInfo_bool)
        if gameId:
            filterCondition.append(proj_battle.game_id == gameId)
        if battleVersion:
            filterCondition.append(proj_battle.version == battleVersion)
        if _reviewServerStatus:
            filterCondition.append(proj_battle.review_server_status == _reviewServerStatus)
        if _reviewPeopleStatus:
            filterCondition.append(proj_battle.review_people_status == _reviewPeopleStatus)
        if _cheatOp:
            _cheatOp = int(_cheatOp)
            filterCondition.append(proj_battle.cheat_op == _cheatOp)
        if battleType:
            filterCondition.append(proj_battle.type == battleType)
        if inconsistOnly == 'true':
            # 这里需要用== False而非is False来处理
            # https://stackoverflow.com/questions/18998010/flake8-complains-on-boolean-comparison-in-filter-clause
            filterCondition.append(proj_battle.consist_status == False)  # noqa
        if multiStatus == 0:
            filterCondition.append(proj_battle.multi_status == False)  # noqa
        elif multiStatus == 1:
            filterCondition.append(proj_battle.multi_status == True)  # noqa
        if teamOnly == 'true':
            filterCondition.append(proj_battle.player_counts > 1)
        if len(filterCondition) > 0:
            battleQuery = db.session.query(proj_battle).filter(and_(*filterCondition)).order_by(proj_battle.end_time.desc())
        else:
            battleQuery = db.session.query(proj_battle).order_by(proj_battle.end_time.desc())

        if playerQuery:
            threshold = 1000000
            if battleQuery.count() > threshold and playerQuery.count() > threshold:
                battleQuery = battleQuery.limit(threshold)

            battleSubquery = battleQuery.subquery()
            playerSubquery = playerQuery.subquery()
            query = db.session.query(battleSubquery)\
                .join(playerSubquery, battleSubquery.c.game_id == playerSubquery.c.battle_id)\
                .order_by(battleSubquery.c.end_time.desc())
            allPageCount = query.count()
            if allPageCount > (pageNo - 1) * pageSize:
                validSubqueryData = query.paginate(page=pageNo, per_page=pageSize)
                for row in validSubqueryData:
                    battle_instance = C1_Battle(**{column.name: getattr(row, column.name) for column in battleSubquery.c})
                    validBattleData.append(battle_instance)
        else:
            query = battleQuery.order_by(proj_battle.end_time.desc())
            allPageCount = query.count()
            if allPageCount > (pageNo - 1) * pageSize:
                validBattleData = query.paginate(page=pageNo, per_page=pageSize)

    jsonBattleData = [_battleProjection.battleToDict() for _battleProjection in validBattleData]
    retData = {
        "pageSize": pageSize,
        "pageNo": pageNo,
        "totalCount": allPageCount,
        "totalPage": allPageCount / pageSize,
        "data": jsonBattleData
    }
    app.logger.info(f'czx getBattleList retData {retData}')
    return jsonify({
        'result': retData
    })


# 迭代为数据库交互
@app.route('/battleDetail', methods=['GET'])
def getBattleDetail():
    gameId = request.args.get('battleId').replace(" ", "+")
    project = request.args.get('project')

    versionList = [float(x) for x in request.args.getlist('version[]')]
    serverNameList = request.args.getlist('serverName[]')
    pageNo = request.args.get('pageNo')
    pageSize = request.args.get('pageSize')
    app.logger.info(f'battleList args is:  project:{project}, version: {versionList}, serverName: {serverNameList}, '
                    f'pageNo: {pageNo}, pageSize: {pageSize}')

    proj_battle = C1_Battle
    query = proj_battle.query.filter(proj_battle.game_id == gameId)
    validBattleData = query.all()
    jsonBattleData = [_battleProjection.battleToDict() for _battleProjection in validBattleData]

    retData = {
        "pageSize": 2,
        "pageNo": 1,
        "totalCount": 1,  # totalCount设置为1让分页功能不显示
        "totalPage": 10,
        "data": jsonBattleData
    }
    return jsonify({
        'result': retData
    })


# 迭代为数据库交互
@app.route('/playerList', methods=['GET'])
def getPlayerList():
    battleId = request.args.get('battleId').replace(" ", "+")
    project = request.args.get('project')

    versionList = [float(x) for x in request.args.getlist('version[]')]
    serverNameList = request.args.getlist('serverName[]')
    pageNo = request.args.get('pageNo')
    pageSize = request.args.get('pageSize')
    app.logger.info(f'battleList args is:  project:{project}, version: {versionList}, serverName: {serverNameList}, '
                    f'pageNo: {pageNo}, pageSize: {pageSize}')

    jsonPlayerData = []
    players = C1_Player.query.filter_by(battle_id=battleId)
    if players:
        jsonPlayerData = [player.playerToDict() for player in players]

    retData = {
        "pageSize": 2,
        "pageNo": 1,
        "totalCount": 1,
        "totalPage": 10,
        "data": jsonPlayerData
    }
    return jsonify({
        'result': retData
    })


@app.route("/reviewServerStatus", methods=["POST"])
def reviewServerStatus():
    # 设置reviewServer的状态
    # 设置优先级/设置重新校验
    data = request.get_json()
    battleId = data.get('battleId')
    # 根据当前status有两种状态
    # 如果当前为NotYet,那么targetStatus为up,优先校验
    # 如果当前为Fail/Pass,那么targetStatus为review，重新校验
    targetStatus = data.get('targetStatus')
    app.logger.info(f"reviewServerStatus {battleId=} {targetStatus=}")
    if not battleId or not targetStatus:
        return {
            "code": retCode.ReviewStatusRetCode.RequestArgsError
        }
    ret = mysqlImp.updateReviewServerStatusWeb(battleId, targetStatus)

    retData = {"code": ret}
    app.logger.info(f"reviewServerStatus {retData} End")
    return jsonify(retData)


@app.route('/reviewServerCheck', methods=['POST'])
def reviewServerCheck():
    # 设置reviewServer的状态
    # 设置校验成功/失败
    data = request.get_json()
    battleId = data.get('battleId', '')
    # 根据当前status有两种状态
    targetStatus = data.get('targetStatus', '')
    app.logger.info(f"reviewServerCheck {battleId=} {targetStatus=}")
    retData = {}
    if targetStatus not in ['Pass', 'Fail']:
        retData['code']: retCode.ReviewStatusRetCode.RequestArgsError
        app.logger.info(f"gmReviewServerCheck {retData} End")
        return jsonify(retData)
    else:
        retData['code'] = mysqlImp.updateReviewServerStatusAuto(battleId, targetStatus)
        if targetStatus == 'Fail':
            playerId = redisImp.setRankBattleCheat(battleId)
            if playerId:
                app.logger.info(f"setRankBattleCheat {battleId=} {playerId=}")
                rankBattleInfos = redisImp.checkPlayerCheckCount(playerId)
                if rankBattleInfos:
                    rankIds, battleIds = zip(*[item.split(':') for item in rankBattleInfos])
                    app.logger.info(f"checkPlayerCheckCount {battleId=} {playerId=} {rankIds=} {battleIds=}")
                    requestImp.autoDelRankToGameServer(battleId, rankIds)
                    redisImp.addAutoDelRankRecord(playerId, rankBattleInfos)
                    redisImp.clearPlayerCheckCount(playerId)
    app.logger.info(f"reviewServerCheck {retData} End")
    return jsonify(retData)


@app.route('/gmReviewServerCheck', methods=['POST'])
def gmReviewServerCheck():
    # GM设置reviewServer的状态
    # 设置校验成功/失败
    data = request.get_json()
    battleId = data.get('battleId', '')
    # 根据当前status有两种状态
    targetStatus = data.get('targetStatus', '')
    app.logger.info(f"gmReviewServerCheck {battleId=} {targetStatus=}")
    retData = {}
    if targetStatus not in ['Pass', 'Fail']:
        retData['code']: retCode.ReviewStatusRetCode.RequestArgsError
        app.logger.info(f"gmReviewServerCheck {retData} End")
        return jsonify(retData)
    retData['code'] = mysqlImp.updateReviewServerStatusAuto(battleId, targetStatus)
    if targetStatus == 'Fail':
        playerId = redisImp.setRankBattleCheat(battleId)
        if playerId:
            app.logger.info(f"setRankBattleCheat {battleId=} {playerId=}")
            rankBattleInfos = redisImp.checkPlayerCheckCount(playerId)
            if rankBattleInfos:
                rankIds, battleIds = zip(*[item.split(':') for item in rankBattleInfos])
                app.logger.info(f"checkPlayerCheckCount {battleId=} {playerId=} {rankIds=} {battleIds=}")
                requestImp.autoDelRankToGameServer(playerId, rankIds)
                redisImp.addAutoDelRankRecord(playerId, rankBattleInfos)
                redisImp.clearPlayerCheckCount(playerId)
    app.logger.info(f"gmReviewServerCheck {retData} End")
    return jsonify(retData)


@app.route('/gmSendToGameServer', methods=['POST'])
def gmSendToGameServer():
    data = request.get_json()
    battleId = data.get('battleId', '')
    app.logger.info(f"gmSendToGameServer {battleId=}")

    retData = {}
    app.logger.info(f"gmSendToGameServer {retData} End")
    return jsonify(retData)


@app.route('/aceCheck', methods=['POST'])
def aceCheck():
    # 设置ace玩家的状态
    # 找出ace玩家的最近10场，都设置为作弊
    data = request.get_json()
    roleId = data.get('roleId', '')
    app.logger.info(f"aceCheck {roleId=}")

    # ret = mysqlImp.updateRoleAceCheckStatus(roleId)
    retData = {}

    app.logger.info(f"aceCheck {retData} End")
    return jsonify(retData)


@app.route("/reviewPeopleStatus", methods=["POST"])
def reviewPeopleStatus():
    # 设置reviewPeople的状态
    # 设置校验结果
    data = request.get_json()
    battleId = data.get('battleId')
    targetStatus = data.get('targetStatus')
    app.logger.info(f"reviewPeopleStatus {battleId=} {targetStatus=}")
    if not battleId or not targetStatus:
        return {
            "code": retCode.ReviewStatusRetCode.RequestArgsError
        }
    ret = mysqlImp.updateReviewPeopleStatus(battleId, targetStatus)

    retData = {"code": ret}
    app.logger.info(f"reviewPeopleStatus {retData} End")
    return jsonify(retData)


@app.route("/reviewPeopleComment", methods=["POST"])
def reviewPeopleComment():
    # 设置reviewPeople的备注
    data = request.get_json()
    battleId = data.get('battleId')
    peopleComment = data.get('peopleComment')
    app.logger.info(f"reviewPeopleComment {battleId=} {peopleComment=}")
    if not battleId or peopleComment is None:
        return {
            "code": retCode.ReviewStatusRetCode.RequestArgsError
        }
    ret = mysqlImp.updateReviewPeopleComment(battleId, peopleComment)

    retData = {"code": ret}
    app.logger.info(f"reviewPeopleComment {retData} End")
    return jsonify(retData)


@app.route("/uploadMemoryStatistic", methods=["POST"])
def uploadMemoryStatistic():
    # JSON对象格式
    # uploadInfo = {
    #     "battleType": "tianshi",
    #     "title": "甜食战场",
    #     "heroDefault": 10,
    #     "monsterDefault": 20,
    #     "bossDefault": 15,
    #     "heroMax": 8,
    #     "monsterMax": 15,
    #     "bossMax": 11,
    # }

    uploadInfo = pickle.loads(b64decode(request.data))

    project = uploadInfo.pop("project", "c1")
    app.logger.info(f"uploadMemoryStatistic {project}")
    if project == "c1" or project == "C1":
        gameId = uploadInfo.pop("gameId", "")
        battle_type = uploadInfo.pop("battleType", "all")
        redisImp.addMemoryData(uploadInfo, gameId, battle_type)
        # mysqlImp.addMemoryData(uploadInfo, gameId, battle_type)
        app.logger.info(f"memory {gameId} {battle_type}")
    app.logger.info(f"uploadMemoryStatistic {project} End")
    return 'uploadMemoryStatistic Return'


@app.route("/memoryDetailData", methods=['GET'])
def getMemoryDetailData():
    type = request.args.get('type')
    if not type:
        return jsonify({"error": "please input type"})
    return jsonify(redisImp.getMemoryDetailData(type))


@app.route("/memoryData", methods=['GET'])
def getMemoryData():
    return jsonify(redisImp.getMemoryData())


@app.route("/memoryData", methods=['DELETE'])
def deleteMemoryData():
    type = request.args.get('type')
    try:
        redisImp.deleteMemoryData(type)
        return "deleteMemoryData return"
    except Exception as e:
        app.logger.error(e)
        return "deleteMemoryData error"


@app.route("/uploadWeeklyTraffic", methods=["POST"])
def uploadWeeklyTraffic():
    uploadInfo = pickle.loads(b64decode(request.data))
    gameId = uploadInfo.pop("gameId", "")
    gameMode = uploadInfo.pop("gameMode", "")
    app.logger.info(f"uploadWeeklyTraffic {gameId} {gameMode}")
    redisImp.addTrafficData(uploadInfo, gameId, gameMode)
    return 'uploadWeeklyTraffic Return'


@app.route("/trafficData", methods=['GET'])
def getTrafficData():
    return jsonify(redisImp.getTrafficData())


@app.route("/trafficData", methods=['DELETE'])
def deleteTrafficData():
    type = request.args.get('type')
    try:
        redisImp.deleteTrafficData(type)
        return "deleteTrafficData return"
    except Exception as e:
        app.logger.error(e)
        return "deleteTrafficData error"
# endregion
