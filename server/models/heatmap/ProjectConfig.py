# -*- coding: utf-8 -*-
from exts import db


class ProjectConfig(db.Model):
    # __bind_key__ = 'map_db'
    __tablename__ = "project_config"

    p_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    p_code = db.Column(db.String(255), unique=True)
    created_time = db.Column(db.DateTime)

    def ProjectConfigToDict(self):
        return {"projectID": self.p_id, "projectName": self.p_code, "createdTime": str(self.created_time)}
