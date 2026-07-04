# -*- coding: utf-8 -*-
from exts import db


class WarningConfig(db.Model):
    # __bind_key__ = 'map_db'
    __tablename__ = "warning_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    p_code = db.Column(db.String(255))
    key = db.Column(db.String(255))
    allow_value = db.Column(db.Numeric(precision=12, scale=2))
    danger_value = db.Column(db.Numeric(precision=12, scale=2))

    def WarningConfigToDict(self):
        return {
            "id": self.id,
            "projectName": self.p_code,
            "typeName": self.key,
            "allowValue": self.allow_value,
            "dangerValue": self.danger_value
        }
