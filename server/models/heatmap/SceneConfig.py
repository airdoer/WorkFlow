# -*- coding: utf-8 -*-
from exts import db


class SceneConfig(db.Model):
    # __bind_key__ = 'map_db'
    __tablename__ = "scene_config"

    scene_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    p_code = db.Column(db.String(255))
    scene_name = db.Column(db.String(255))
    img_addr = db.Column(db.String(255))
    data_addr = db.Column(db.String(255))
    upload_date = db.Column(db.DateTime)
    leftBottom = db.Column(db.String(255))
    rightTop = db.Column(db.String(255))

    def SceneConfigToDict(self):
        return {"id": self.scene_id, "projectName": self.p_code, "sceneName": self.scene_name,
                "imgFile": self.img_addr, "dataFile": self.data_addr, "uploadDate": str(self.upload_date),
                "leftBottom": self.leftBottom, "rightTop": self.rightTop}
