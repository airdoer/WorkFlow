from exts import db
from sqlalchemy.dialects.mysql import LONGBLOB


class Player(db.Model):
    __tablename__ = "c3_players"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    player_id = db.Column(db.String(255), index=True)
    name = db.Column(db.String(255), index=True)
    app_edition = db.Column(db.String(255))
    os = db.Column(db.String(255))
    os_edition = db.Column(db.String(255))
    device_name = db.Column(db.String(255))
    device_edition = db.Column(db.String(255))
    device_id = db.Column(db.String(255))

    start_time = db.Column(db.DateTime)
    battle_id = db.Column(db.String(255))

    hash_frame = db.Column(db.Integer)  # 玩家不一致的帧号
    hash_value = db.Column(db.String(255))  # 玩家不一致的hash值
    snapshot_frame = db.Column(db.Integer)  # 玩家不一致后最近的snapshot的帧号
    snapshot_hash = db.Column(db.String(255))  # 玩家不一致后最近的snapshot的hash
    snapshot_value = db.Column(LONGBLOB)  # 玩家不一致后最近的snapshot

    # 定义索引
    __table_args__ = (
        db.Index('idx_start_time', start_time.desc()),
    )

    def playerToDict(self):
        return {"playerName": self.name, "playerId": self.player_id, "appEdition": self.app_edition, "os": self.os,
                "osEdition": self.os_edition, "deviceName": self.device_name,
                "deviceEdition": self.device_edition, 'startTime': self.start_time,
                "deviceId": self.device_id, "id": self.id, "hashFrame": self.hash_frame, "hashValue": self.hash_value,
                "snapshotFrame": self.snapshot_frame, "snapshotHash": self.snapshot_hash}
