from exts import db


class Player(db.Model):
    __tablename__ = "players"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    player_id = db.Column(db.String(255), index=True)
    role_id = db.Column(db.Integer, index=True)
    name = db.Column(db.String(255), index=True)
    server_name = db.Column(db.String(255))
    app_edition = db.Column(db.String(255))
    local_engine_version = db.Column(db.String(255), index=True)
    local_patch_version = db.Column(db.String(255), index=True)
    prev_patch_version = db.Column(db.String(255), index=True)
    os = db.Column(db.String(255))
    os_edition = db.Column(db.String(255))
    device_name = db.Column(db.String(255))
    device_edition = db.Column(db.String(255))
    device_id = db.Column(db.String(255))

    start_time = db.Column(db.DateTime)
    battle_id = db.Column(db.String(255), index=True)

    hash_frame = db.Column(db.Integer)  # 玩家不一致的帧号
    hash_value = db.Column(db.String(255))  # 玩家不一致的hash值
    order = db.Column(db.Integer)

    # 定义索引
    __table_args__ = (
        db.Index('idx_start_time', start_time.desc()),
    )

    def playerToDict(self):
        return {"playerName": self.name, "playerId": self.role_id, "appEdition": self.app_edition,
                "localEngineVersion": self.local_engine_version, "localPatchVersion": self.local_patch_version,
                "os": self.os, "osEdition": self.os_edition, "deviceName": self.device_name,
                "deviceEdition": self.device_edition, 'startTime': self.start_time, 'order': self.order,
                "deviceId": self.device_id, "id": self.id, "hashFrame": self.hash_frame, "hashValue": self.hash_value}
