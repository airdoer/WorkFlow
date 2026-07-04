from exts import db
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy import Enum


class Battle(db.Model):
    __tablename__ = "battles"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.String(255), index=True)
    player_names = db.Column(db.String(255))
    server_name = db.Column(db.String(255), index=True)
    version = db.Column(db.String(255), index=True)
    battle_server_version = db.Column(db.String(255))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.String(255))
    consist_status = db.Column(db.Boolean, index=True)
    multi_status = db.Column(db.Boolean)
    end_status = db.Column(db.Boolean)
    sync_status = db.Column(db.Boolean)
    player_counts = db.Column(db.Integer, index=True)
    inconsistent_frame_counts = db.Column(db.Integer)
    type = db.Column(db.String(255), index=True)
    replayData = db.Column(LONGBLOB)  # LargeBinary这样定义就可以从blob变成longblob类型
    # review_score = db.Column(db.Integer)  # review分数，0-100，越大越需要校验，0以下无需校验
    cheat_op = db.Column(db.Integer, index=True)

    # reviewServer的校验状态 NotYet还未校验/Checking正在校验/Pass校验通过/Fail校验失败，增加按钮（插队自动校验）
    review_server_status = db.Column(
        Enum('NotYet', 'Pass', 'Fail', 'Checking', name='review_server_status'),
        nullable=False,
        default='NotYet',
        index=True
    )

    # review人工的校验状态 NotYet还未校验/Pass校验通过/Fail校验失败，增加按钮（设置校验结果）
    review_people_status = db.Column(
        Enum('NotYet', 'Pass', 'Fail', 'Checking', name='review_people_status'),
        nullable=False,
        default='NotYet',
        index=True
    )

    judge_cheat_reason = db.Column(db.String(255))  # 服务端判断的作弊原因

    people_comment = db.Column(db.String(255))  # 人工校验备注

    # 创建start_time降序索引
    __table_args__ = (
        db.Index('idx_start_time', start_time.desc()),
        db.Index('idx_end_time', end_time.desc()),
        db.Index('idx_cheat_op', cheat_op.desc()),
    )

    def battleToDict(self):
        # 返回给前段的战斗信息
        return {
            "gameId": self.game_id,
            "playerNames": self.player_names,
            "serverName": self.server_name,
            "version": self.version,
            "battleServerVersion": self.battle_server_version,
            "startTime": str(self.start_time),
            "endTime": str(self.end_time),
            "duration": self.duration,
            "consistStatus": self.consist_status,
            "singleStatus": not self.multi_status,
            "syncStatus": self.sync_status,
            "playerCounts": self.player_counts,
            "inconsistentFrameCounts": self.inconsistent_frame_counts,
            "type": self.type,
            "endStatus": self.end_status,
            "cheatOp": self.cheat_op,
            "reviewServerStatus": self.review_server_status,
            "reviewPeopleStatus": self.review_people_status,
            'judgeCheatReason': self.judge_cheat_reason,
            'peopleComment': self.people_comment,
        }
