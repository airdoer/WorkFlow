from exts import db


class Room(db.Model):
    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.String(255), index=True)
    room_id = db.Column(db.String(255))
    frame_id = db.Column(db.Integer)

    def roomToDict(self):
        return {"gameId": self.battle_id, "roomId": self.room_id, "frameId": self.frame_id}
