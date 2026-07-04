
KEY_STORAGE_FORMAT = "{battle_%s_%s}_storage_%s"
BATTLE_ROOM_SNAPSHOT_FORMAT = "{battle_room_snapshot_%s_%s}_%s"


def _getCosStorageKey(server_name, key, battle_id):
    return KEY_STORAGE_FORMAT % (server_name, battle_id, key)


def _getCosRoomSnapshotKey(server_name, battle_id, room_id):
    return BATTLE_ROOM_SNAPSHOT_FORMAT % (server_name, battle_id, room_id)


def _getCosServerName(server_name):
    if not server_name or server_name == "":
        server_name = "c1_common"
    elif server_name == "深海公共服":
        server_name = "c1_common"
    elif server_name == "甜食服务器":
        server_name = "c1_common150"
    return server_name
