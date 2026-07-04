# 和游戏服务器 战斗相关的route放这个里 这里只放对内的接口 对外的放battleExternal里

# builtin
from datetime import datetime
import os
import uuid
import subprocess
import re

# 3rd ext
from flask import render_template, request, jsonify, Response
from sqlalchemy import and_
import io
import csv

# int
from appImp import app
from Implement.hotfixImpl import p4Imp
from Implement.hotfixImpl import hotfixImp
from utility import p4Utils
import config
import json
from managers.timeMgr import cron
# region init

@app.route('/getServerConfig', methods=['GET'])
def getServerConfig():
    
    return jsonify({
        'code': 0,
        'success': True,
        'data': {
        }
    }), 200