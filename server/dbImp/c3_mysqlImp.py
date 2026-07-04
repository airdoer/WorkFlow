from exts import db
from datetime import datetime
from models.c3.battle import Battle
from models.c3.player import Player


def battleAdd(battleData):
    for battleItem in battleData:
        battle = Battle(game_id=battleItem["gameId"], player_names=battleItem["playerNames"],
                        server_name=battleItem["serverName"], version=battleItem["version"],
                        start_time=battleItem["startTime"],
                        duration=battleItem["duration"], consist_status=battleItem["consistStatus"],
                        play_counts=battleItem["playCounts"],
                        inconsistent_frame_counts=battleItem["inconsistentFrameCounts"])
        for playerData in battleItem["playerList"]:
            player = Player(name=playerData["playerName"], app_edition=playerData["appEdition"], os=playerData["os"],
                            os_edition=playerData["osEdition"], device_name=playerData["deviceName"],
                            device_edition=playerData["deviceEdition"], device_id=playerData["deviceId"],
                            stop_frame=playerData["stopFrame"], start_time=battleItem['startTime'])
            battle.players.append(player)
        db.session.add(battle)
        db.session.commit()


def addBattleData(battleData):
    server_name = battleData["serverName"]

    duration = int(battleData["duration"])
    minute = duration // 60
    second = duration % 60
    duration = str(minute) + "分" + str(second) + "秒"
    start_time = datetime.fromtimestamp(float(battleData["startTs"]) + 60 * 60 * 8)
    battle = Battle(
        game_id=battleData['battleId'],
        player_names=";".join([x['name'] for x in battleData['playerInfos']]),
        server_name=server_name,
        version=battleData["version"],
        start_time=start_time,
        duration=duration,
        consist_status=battleData["consistStatus"],
        player_counts=len(battleData["playerInfos"]),
        inconsistent_frame_counts=battleData["inconsistentFrameCounts"],  # 不一致帧
        replayData=battleData["replay"],
    )
    # 不一致当帧玩家的hash  { playerId: (firstConsistIdx, hashCode) }
    inconsistentPlayerInfo = battleData['inconsistentPlayerInfo']
    inconsistentSnapshotInfo = battleData['inconsistentSnapshotInfo']

    for playerData in battleData['playerInfos']:
        player_id = playerData['id']  # 游戏中的role_id
        player = Player(
            player_id=player_id,
            name=playerData["name"],
            app_edition=playerData["appEdition"],
            os=playerData["os"],
            os_edition=playerData["osEdition"],
            device_name=playerData["deviceName"],
            device_edition=playerData["deviceEdition"],
            device_id=playerData["deviceId"],
            # stop_frame=playerData.get("stopFrame", 0),  # 目前没有用
            hash_frame=inconsistentPlayerInfo.get(player_id, [-1, ""])[0],  # 玩家不一致的帧号
            hash_value=inconsistentPlayerInfo.get(player_id, [-1, ""])[1],  # 玩家不一致的hash值
            snapshot_frame=inconsistentSnapshotInfo.get(player_id, [-1, "", b""])[0],  # 玩家不一致后最近的snapshot的帧号
            snapshot_hash=inconsistentSnapshotInfo.get(player_id, [-1, "", b""])[1],  # 玩家不一致后最近的snapshot的hash
            snapshot_value=inconsistentSnapshotInfo.get(player_id, [-1, "", b""])[2],  # 玩家不一致后最近的snapshot
            start_time=start_time,
            battle_id=battleData['battleId'],
        )

        db.session.add(player)

    db.session.add(battle)
    db.session.commit()


def getBattleData(game_id) -> Battle:
    battle = Battle.query.filter_by(game_id=game_id).first()
    return battle


def getPlayer(pid) -> Player:
    player = Player.query.filter_by(id=pid).first()
    return player
