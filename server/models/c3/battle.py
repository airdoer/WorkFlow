from exts import db
from sqlalchemy.dialects.mysql import LONGBLOB


class Battle(db.Model):
    __tablename__ = "c3_battles"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.String(255), index=True)
    player_names = db.Column(db.String(255))
    server_name = db.Column(db.String(255))
    version = db.Column(db.String(255))
    start_time = db.Column(db.DateTime)
    duration = db.Column(db.String(255))
    consist_status = db.Column(db.Boolean, index=True)
    player_counts = db.Column(db.Integer)
    inconsistent_frame_counts = db.Column(db.Integer)
    replayData = db.Column(LONGBLOB)  # LargeBinary这样定义就可以从blob变成longblob类型

    # 创建start_time降序索引
    __table_args__ = (
        db.Index('idx_start_time', start_time.desc()),
    )

    def battleToDict(self):
        return {"gameId": self.game_id, "playerNames": self.player_names, "version": self.version,
                "serverName": self.server_name, "startTime": str(self.start_time), "duration": self.duration,
                "consistStatus": self.consist_status, "playerCounts": self.player_counts,
                "inconsistentFrameCounts": self.inconsistent_frame_counts}
