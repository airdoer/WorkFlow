from exts import db
from datetime import datetime, timedelta
from models.c1.battle import Battle
from models.c1.player import Player
from models.c1.room import Room
import pickle
from utility import retCode, cheatUtils
from sqlalchemy import and_
import g


def battleAdd(battleData):
    for battleItem in battleData:
        battle = Battle(game_id=battleItem["gameId"], player_names=battleItem["playerNames"],
                        server_name=battleItem["serverName"], version=battleItem["version"],
                        start_time=battleItem["startTime"],
                        duration=battleItem["duration"], consist_status=battleItem["consistStatus"],
                        play_counts=battleItem["playCounts"],
                        inconsistent_frame_counts=battleItem["inconsistentFrameCounts"])
        for playerData in battleItem["playerList"]:
            player = Player(name=playerData["playerName"], app_edition=playerData["appEdition"],
                            os=playerData.get("platform", ""),
                            os_edition=playerData["osEdition"], device_name=playerData["deviceName"],
                            device_edition=playerData["deviceEdition"], device_id=playerData["deviceId"],
                            stop_frame=playerData["stopFrame"], start_time=battleItem['startTime'])
            battle.players.append(player)
        db.session.add(battle)
        db.session.commit()


def updateCheatStatus(battleId, cheatOp):
    # 设置作弊位或者重点关注位
    g.app.logger.info(f'updateCheatStatus {battleId=} {cheatOp=}')
    query = Battle.query.filter(Battle.game_id == battleId).first()
    if query:
        if query.cheat_op is None or cheatUtils.cheatOpCanOverride(query.cheat_op, cheatOp):
            query.cheat_op = cheatOp
            db.session.commit()
            return retCode.CheatStatusRetCode.UpdateSuccess
        else:
            return retCode.CheatStatusRetCode.AlreadyHasCheatFlag
    else:
        return retCode.CheatStatusRetCode.BattleNotExist


def updateCheatStatusRetry(battleId, cheatOp):
    with g.app.app_context():
        g.app.logger.info(f'updateCheatStatusRetry {battleId=} {cheatOp=}')
        updateCheatStatus(battleId, cheatOp)


def setBattleChecking(battleId):
    # 设置mysql中对应战场为正在校验
    query = Battle.query.filter(Battle.game_id == battleId).first()
    if query:
        query.review_server_status = 'Checking'
        db.session.commit()
    else:
        g.app.logger.info(f'setBattleChecking {battleId} not exist')


def getCheckBattleIds(cnt):
    # 需要找2分钟之前的，防止因为录像上传还没结束，导致下载失败
    end_time_datetime = datetime.utcnow() + timedelta(hours=8) - timedelta(minutes=2)
    start_time_datetime = datetime.utcnow() + timedelta(hours=8) - timedelta(hours=2)
    filterCondition = [
        Battle.review_server_status == 'NotYet',
        Battle.type.in_(['NORMAL_PVE', "ABYSS", "DQQ_PVE", "DQQ_MIRROR_PVP", "ENDLESS_BOSS", "WORLD_BOSS_HUGE"]),
        Battle.end_time < end_time_datetime,
        Battle.end_time >= start_time_datetime,
        Battle.sync_status.is_(True)
    ]
    results = Battle.query.with_entities(Battle.game_id).\
        filter(and_(*filterCondition)).order_by(Battle.end_time.desc()).limit(cnt).all()

    return [result[0] for result in results]


def updateReviewServerStatusWeb(battleId, targetStatus):
    # 这里的targetStatus是'review'，也就是重新校验
    query = Battle.query.filter(Battle.game_id == battleId).first()
    if query:
        if targetStatus == 'resetup':
            query.review_server_status = 'NotYet'
            db.session.commit()
            from dbImp import redisImp
            redisImp.upCheckBattleId(battleId)
            return retCode.ReviewStatusRetCode.UpSuccess
        elif targetStatus == 'review':
            if query.review_server_status in ['Pass', 'Fail', 'Checking']:
                query.review_server_status = 'NotYet'
                db.session.commit()
                return retCode.ReviewStatusRetCode.ReviewSuccess
            else:
                return retCode.ReviewStatusRetCode.SetReviewNotYet
        elif targetStatus == 'up':
            if query.review_server_status in ['Pass', 'Fail']:
                return retCode.ReviewStatusRetCode.SetUpButAlready
            else:
                from dbImp import redisImp
                redisImp.upCheckBattleId(battleId)
                return retCode.ReviewStatusRetCode.UpSuccess
        else:
            return retCode.ReviewStatusRetCode.RequestArgsError
    else:
        return retCode.ReviewStatusRetCode.BattleNotExist


def updateReviewServerStatusAuto(battleId, targetStatus):
    # 由DedicatedServer校验完成后调用的，所以targetStatus只有Pass/Fail
    query = Battle.query.filter(Battle.game_id == battleId).first()
    if query:
        query.review_server_status = targetStatus
        db.session.commit()
        return retCode.ReviewStatusRetCode.CheckSuccess
    else:
        return retCode.ReviewStatusRetCode.BattleNotExist


def updateReviewPeopleStatus(battleId, targetStatus):
    query = Battle.query.filter(Battle.game_id == battleId).first()
    if query:
        query.review_people_status = targetStatus
        db.session.commit()
        return retCode.ReviewStatusRetCode.CheckSuccess
    else:
        return retCode.ReviewStatusRetCode.BattleNotExist


def updateReviewPeopleComment(battleId, comment):
    query = Battle.query.filter(Battle.game_id == battleId).first()
    if query:
        query.people_comment = comment
        db.session.commit()
        return retCode.ReviewStatusRetCode.CommentSuccess
    else:
        return retCode.ReviewStatusRetCode.BattleNotExist


def getHighReviewScoreBattles(batch_size=10):
    # 这是projection优化，返回特定数据，这样可以省去replay的数据传输
    battleFields = [Battle.game_id]
    filterCondition = [Battle.review_server_status == 'NotYet', Battle.review_people_status > 0]
    query = db.session.query(*battleFields).filter(and_(*filterCondition)).limit(batch_size)
    validBattleData = query.all()
    print(f'getHighReviewScore {validBattleData}')
    import g
    g.testData = validBattleData
    return validBattleData


def addBattleData(battleData):
    server_name = battleData["serverName"]
    if server_name == "c1_common":
        server_name = "深海公共服"
    elif server_name == "c1_common150":
        server_name = "甜食服务器"

    offset = 60 * 60 * 8
    start_time = datetime.fromtimestamp(float(battleData["startTs"]) + offset)

    # 不一致当帧玩家的hash  { playerId: (firstConsistIdx, hashCode) }
    inconsistentPlayerInfo = battleData.get('inconsistentPlayerInfo', {})

    query = Battle.query.filter(Battle.game_id == battleData['battleId']).first()
    if query:
        updateBattleData(query, battleData)
    else:
        playerIndex = battleData.get('playerIndex', {})
        playerInfos = battleData['playerInfos']
        playerNames = []
        for x in playerInfos:
            if len(playerNames) > 5:
                break
            index = playerIndex.get(x['roleId'])
            if index is not None:
                name = str(index) + ': ' + x['name']
            else:
                name = x['name']
            playerNames.append(name)
        battle = Battle(
            game_id=battleData['battleId'],
            player_names="; ".join(playerNames),
            server_name=server_name,
            version=battleData["version"],
            start_time=start_time,
            end_time=datetime.fromtimestamp(float(battleData["endTs"]) + offset),
            duration=battleData.get('duration', 0),
            consist_status=battleData["consistStatus"],
            multi_status=False,
            end_status=False,
            sync_status=not battleData.get('useBattleServer', False),  # 是否帧同步
            battle_server_version=battleData.get('battleServerVersion', ""),
            player_counts=len(playerInfos),
            inconsistent_frame_counts=battleData["inconsistentFrameCounts"],
            type=battleData.get("levelType", ""),
            replayData=battleData.get("replay", b""),
            cheat_op=battleData.get("cheatOp", 0),
            review_server_status='NotYet',
            review_people_status='NotYet',
            judge_cheat_reason=battleData.get("judgeCheatReason", ''),  # judge_cheat_reason
        )

        for playerData in battleData['playerInfos']:
            player_id = playerData['roleId']  # 游戏中的role_id
            player = Player(
                player_id=playerData['id'],
                role_id=playerData.get('roleId'),
                name=playerData["name"],
                server_name=server_name,
                local_engine_version=playerData["localEngineVersion"],
                local_patch_version=playerData["localPatchVersion"],
                os=playerData.get("platform", ""),
                os_edition=playerData["osEdition"],
                device_name=playerData["deviceName"],
                device_edition=playerData["deviceEdition"],
                device_id=playerData["deviceId"],
                hash_frame=inconsistentPlayerInfo.get(player_id, [-1, ""])[0],  # 玩家不一致的帧号
                hash_value=inconsistentPlayerInfo.get(player_id, [-1, ""])[1],  # 玩家不一致的hash值
                start_time=start_time,
                battle_id=battleData['battleId'],
                order=playerIndex.get(player_id, 0),
            )

            db.session.add(player)

        db.session.add(battle)

    db.session.commit()


def updateBattleData(query, battleData):
    query.version = battleData["version"]
    query.end_time = datetime.fromtimestamp(float(battleData["endTs"]) + 60 * 60 * 8)

    query.consist_status = query.consist_status and battleData["consistStatus"]
    query.multi_status = True
    query.end_status = False

    if query.inconsistent_frame_counts == -1:
        query.inconsistent_frame_counts = battleData["inconsistentFrameCounts"]

    if query.replayData and battleData.get("replay"):
        prevReplay = pickle.loads(query.replayData)
        currReplay = pickle.loads(battleData["replay"])
        prevReplay['frameInfo'].extend(currReplay['frameInfo'])
        query.replayData = pickle.dumps(prevReplay)

    duration = battleData.get('duration')
    if duration and duration > 0:
        query.duration = duration

    query = Player.query.filter(Player.battle_id == battleData['battleId']).first()
    playerData = battleData['playerInfos'][0]

    query.local_engine_version = playerData["localEngineVersion"]
    if query.local_patch_version != playerData["localPatchVersion"]:
        query.prev_patch_version = query.local_patch_version
        query.local_patch_version = playerData["localPatchVersion"]
    query.os = playerData.get("platform", "")
    query.os_edition = playerData["osEdition"]
    query.device_name = playerData["deviceName"]
    query.device_edition = playerData["deviceEdition"]
    query.device_id = playerData["deviceId"]


def addRoomInfo(roomData):
    room = Room(
        game_id=roomData['battleId'],
        room_id=roomData['roomId'],
        frame_id=roomData['frameId'],
    )
    db.session.add(room)
    db.session.commit()


def getBattleData(game_id) -> Battle:
    battle = Battle.query.filter_by(game_id=game_id).first()
    return battle


def getRooms(game_id):
    rooms = Room.query.filter_by(game_id=game_id)
    return rooms


def getPlayer(pid) -> Player:
    player = Player.query.filter_by(id=pid).first()
    return player
