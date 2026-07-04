# 和游戏服务器 战斗相关的route放这个里

# builtin
import json
import logging
import pickle
from base64 import b64encode
from io import BytesIO

# 3rd ext
from flask import request, jsonify, send_file

# int
from appImp import app
from dbImp import mysqlImp
from Implement.battleImp.battleCommonUtils import _getCosStorageKey, _getCosRoomSnapshotKey, _getCosServerName

from lib.object_storage.server import cos_implement
from lib.object_storage.server import config as cos_config

# region init
# cos_implement.init_cos_client()
# endregion


# region route
def getServerName(game_id):
    battleData = mysqlImp.getBattleData(game_id)
    if not battleData:
        return 'online'
    else:
        return _getCosServerName(battleData.server_name)


@app.route('/downloadBattle', methods=['GET'])
def downloadBattle():
    app.logger.info("downloadBattle")
    game_id = request.args.get('battleId').replace(" ", "+")
    project = request.args.get('project')
    logging.info(f'czx downloadBattle {game_id} {project}')

    server_name = request.args.get('server') or getServerName(game_id)
    roomInfo = mysqlImp.getRooms(game_id)
    key = _getCosStorageKey(server_name, 'battle_replay', game_id)
    try:
        cosRet = cos_implement.download_object_stream(cos_config.TEST_BUCKET_NAME, key)
        replayData = json.loads(cosRet.data)
    except cos_implement.cos_exceptions as e:
        if getattr(e, '_digest_msg').get('code') == 'NoSuchKey':
            return jsonify({
                'error': f'no battle replay {game_id}'
            })
        raise e

    startInfo = replayData['startInfo']
    rooms = {}
    if roomInfo:
        for room in roomInfo:
            rooms[room.room_id] = room.frame_id

    return jsonify({
        'startInfo': startInfo,
        'frameInfo': replayData['frameInfo'],
        'hashInfo': replayData.get('hashInfo', {}),
        'rooms': rooms,
        'game_id': game_id,
        'server_name': server_name,
    })


@app.route('/downloadBattleFile', methods=['GET'])
def downloadBattleFile():
    app.logger.info("downloadBattleFile")
    game_id = request.args.get('battleId').replace(" ", "+")
    project = request.args.get('project')
    logging.info(f'czx downloadBattleFile {game_id} {project}')

    server_name = request.args.get('server') or getServerName(game_id)
    roomInfo = mysqlImp.getRooms(game_id)
    key = _getCosStorageKey(server_name, 'battle_replay', game_id)
    try:
        cosRet = cos_implement.download_object_stream(cos_config.TEST_BUCKET_NAME, key)
        replayData = json.loads(cosRet.data)
    except cos_implement.cos_exceptions as e:
        if getattr(e, '_digest_msg').get('code') == 'NoSuchKey':
            return jsonify({
                'error': f'no battle replay {game_id}'
            })
        raise e

    startInfo = replayData['startInfo']
    rooms = {}
    if roomInfo:
        for room in roomInfo:
            rooms[room.room_id] = room.frame_id

    battleFileData = json.dumps({
        'startInfo': startInfo,
        'frameInfo': replayData['frameInfo'],
        'hashInfo': replayData.get('hashInfo', {}),
        'rooms': rooms,
        'game_id': game_id,
        'server_name': server_name,
    }, separators=(',', ':'))

    fileStream = BytesIO(battleFileData.encode("utf-8"))
    fileName = "replay-" + game_id + ".txt"
    return send_file(fileStream, download_name=fileName, as_attachment=True)


@app.route('/downloadBattleSnapshot', methods=['GET'])
def downloadBattleSnapshot():
    app.logger.info("downloadBattleSnapshot")
    game_id = request.args.get('battleId').replace(" ", "+")
    logging.info(f'lyw downloadBattleSnapshot {game_id}')

    server_name = request.args.get('server') or getServerName(game_id)
    key = _getCosStorageKey(server_name, 'battle_snapshot', game_id)
    try:
        cosRet = cos_implement.download_object_stream(cos_config.TEST_BUCKET_NAME, key)
        snapshot = cosRet.data
    except cos_implement.cos_exceptions as e:
        if getattr(e, '_digest_msg').get('code') == 'NoSuchKey':
            return jsonify({
                'error': f'no snapshot data {game_id}'
            })
        raise e

    return jsonify({
        'snapshot': b64encode(snapshot).decode(),
    })


@app.route('/downloadBattleSnapshotFile', methods=['GET'])
def downloadBattleSnapshotFile():
    app.logger.info("downloadBattleSnapshotFile")
    game_id = request.args.get('battleId').replace(" ", "+")
    logging.info(f'lyw downloadBattleSnapshotFile {game_id}')

    server_name = request.args.get('server') or getServerName(game_id)
    key = _getCosStorageKey(server_name, 'battle_snapshot', game_id)
    try:
        cosRet = cos_implement.download_object_stream(cos_config.TEST_BUCKET_NAME, key)
        fileData = cosRet.data
    except cos_implement.cos_exceptions as e:
        if getattr(e, '_digest_msg').get('code') == 'NoSuchKey':
            return jsonify({
                'error': f'no snapshot data {game_id}'
            })
        raise e

    if fileData:
        fileStream = BytesIO(fileData)
        fileName = "snapshot_" + game_id
        return send_file(fileStream, download_name=fileName, as_attachment=True)

    return jsonify({
        'error': f'no snapshot data {game_id}'
    })


@app.route('/downloadSnapshot', methods=['GET'])
def downloadSnapshot():
    app.logger.info("downloadSnapshot")
    pid = request.args.get('id')
    project = request.args.get('project')
    logging.info(f'mtf downloadSnapshot {pid} {project}')

    player = mysqlImp.getPlayer(pid)
    if not player:
        return jsonify({
            'error': f'no player data {pid}'
        })

    server_name = _getCosServerName(player.server_name)
    key = _getCosStorageKey(server_name, 'battle_inconsistent', player.battle_id)
    try:
        cosRet = cos_implement.download_object_stream(cos_config.TEST_BUCKET_NAME, key)
        snapshotData = pickle.loads(cosRet.data)
        frame = snapshotData[player.player_id][0]
        hash = snapshotData[player.player_id][1]
        snapshot = snapshotData[player.player_id][2]
    except cos_implement.cos_exceptions as e:
        if getattr(e, '_digest_msg').get('code') == 'NoSuchKey':
            return jsonify({
                'error': f'no inconsist snapshot data {player.battle_id}'
            })
        raise e

    return jsonify({
        'snapshot': b64encode(snapshot).decode(),
        'id': pid,
        'frame': frame,
        'hash': hash,
    })


@app.route('/downloadSnapshotFile', methods=['GET'])
def downloadSnapshotFile():
    pid = request.args.get('id')
    player = mysqlImp.getPlayer(pid)
    if not player:
        return jsonify({
            'error': f'no player data {pid}'
        })

    server_name = _getCosServerName(player.server_name)
    key = _getCosStorageKey(server_name, 'battle_inconsistent', player.battle_id)
    try:
        cosRet = cos_implement.download_object_stream(cos_config.TEST_BUCKET_NAME, key)
        snapshotData = pickle.loads(cosRet.data)
        fileData = snapshotData[player.player_id][2]
    except cos_implement.cos_exceptions as e:
        if getattr(e, '_digest_msg').get('code') == 'NoSuchKey':
            return jsonify({
                'error': f'no inconsist snapshot data {player.battle_id}'
            })
        raise e

    if fileData:
        fileStream = BytesIO(fileData)
        fileName = "snapshot_" + pid
        return send_file(fileStream, download_name=fileName, as_attachment=True)

    return jsonify({
        'error': f'no snapshot data {pid}'
    })


@app.route('/downloadRoomSnapshot', methods=['GET'])
def downloadRoomSnapshot():
    game_id = request.args.get('battleId').replace(" ", "+")
    room_id = request.args.get('roomId')
    logging.info(f'lyw downloadBattleSnapshot {game_id} {room_id}')

    server_name = request.args.get('server') or getServerName(game_id)
    key = _getCosRoomSnapshotKey(server_name, game_id, room_id)
    try:
        cosRet = cos_implement.download_object_stream(cos_config.TEST_BUCKET_NAME, key)
        snapshot = cosRet.data
    except cos_implement.cos_exceptions as e:
        if getattr(e, '_digest_msg').get('code') == 'NoSuchKey':
            return jsonify({
                'error': f'no snapshot data {game_id}'
            })
        raise e

    return jsonify({
        'snapshot': b64encode(snapshot).decode(),
    })


@app.route('/downloadRoomSnapshotFile', methods=['GET'])
def downloadRoomSnapshotFile():
    game_id = request.args.get('battleId').replace(" ", "+")
    room_id = request.args.get('roomId')
    logging.info(f'lyw downloadBattleSnapshot {game_id} {room_id}')

    server_name = request.args.get('server') or getServerName(game_id)
    key = _getCosRoomSnapshotKey(server_name, game_id, room_id)
    try:
        cosRet = cos_implement.download_object_stream(cos_config.TEST_BUCKET_NAME, key)
        fileData = cosRet.data
    except cos_implement.cos_exceptions as e:
        if getattr(e, '_digest_msg').get('code') == 'NoSuchKey':
            return jsonify({
                'error': f'no snapshot data {game_id}'
            })
        raise e

    if fileData:
        fileStream = BytesIO(fileData)
        fileName = "snapshot_" + game_id + "_" + room_id
        return send_file(fileStream, download_name=fileName, as_attachment=True)

    return jsonify({
        'error': f'no snapshot data {game_id}'
    })
# endregion
