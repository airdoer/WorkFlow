import pytz

from exts import db
from models.heatmap.ProjectConfig import ProjectConfig
from models.heatmap.SceneConfig import SceneConfig
from models.heatmap.WarningConfig import WarningConfig
import datetime


def addScene(sceneData):
    scene = SceneConfig()
    scene.p_code = sceneData.get("projectName")
    scene.scene_name = sceneData.get("sceneName")
    scene.img_addr = sceneData.get("imgFile")
    scene.data_addr = sceneData.get("dataFile")
    scene.upload_date = datetime.datetime.now(pytz.timezone('Asia/Shanghai')).strftime("%Y-%m-%d %H:%M:%S")
    scene.leftBottom = sceneData.get("leftBottom")
    scene.rightTop = sceneData.get("rightTop")
    db.session.add(scene)
    db.session.commit()
    return {
        'status': 'success',
        'message': 'scene添加成功'
    }


def delScene(scene_id):
    scnen = SceneConfig.query.get(scene_id)
    db.session.delete(scnen)
    db.session.commit()
    return {
        'status': 'success',
        'message': 'scene删除成功'
    }


def getSceneBycode(p_code):
    results = SceneConfig.query.filter_by(p_code=p_code).all()
    return results


def getSceneByid(scene_id):
    result = SceneConfig.query.filter_by(scene_id=scene_id).first()
    return result


def getSceneImg(p_code, scene_name):
    result = SceneConfig.query.filter_by(p_code=p_code, scene_name=scene_name).first()
    res_dict = dict()
    res_dict["imgFile"] = result.SceneConfigToDict()["imgFile"]
    res_dict["leftBottom"] = result.SceneConfigToDict()["leftBottom"]
    res_dict["rightTop"] = result.SceneConfigToDict()["rightTop"]
    return res_dict


def addProject(projectData):
    project = ProjectConfig()
    project.p_code = projectData.get("projectName")
    project.created_time = datetime.datetime.now(pytz.timezone('Asia/Shanghai')).strftime("%Y-%m-%d %H:%M:%S")
    db.session.add(project)
    db.session.commit()
    return {
        'status': 'success',
        'message': 'project添加成功'
    }


def delProject(p_code):
    project = ProjectConfig.query.get(p_code)
    if project:
        db.session.delete(project)
        db.session.commit()
        return {
            'status': 'success',
            'message': 'project删除成功'
        }
    else:
        return {
            'status': 'fail',
            'message': 'project不存在'
        }


def getProject(p_code):
    result = ProjectConfig.query.filter_by(p_code=p_code).first()
    return result


def getAllProject():
    result = ProjectConfig.query.all()
    return result

# def upProjectByShow(project_data):
#     p_code = project_data.get("p_code")
#     data = ProjectConfig.query.get(p_code)
#     if data:
#         data.show_items = project_data.get("show_items")
#         db.session.commit()
#         return {
#             'status': 'success',
#             'message': '更新项目show_items成功'
#         }
#     else:
#         return {
#             'status': 'fail',
#             'message': '没有找到项目'
#         }


def addWarning(warnconfigData):
    Warning = WarningConfig(p_code=warnconfigData.get("projectName"), key=warnconfigData.get("typeName"),
                            allow_value=warnconfigData.get("allowValue"), danger_value=warnconfigData.get("dangerValue"))
    db.session.add(Warning)
    db.session.commit()
    return {
        'status': 'success',
        'message': 'Warning config添加成功'
    }


def getWaring(p_code, key):
    result = WarningConfig.query.filter_by(p_code=p_code, key=key).first()
    return result


def getAllWaringByPcode(p_code):
    result = WarningConfig.query.filter_by(p_code=p_code).all()
    return result


def upWaring(warn_data):
    warn_id = warn_data.get("id")
    warn = WarningConfig.query.get(warn_id)
    if warn:
        warn.key = warn_data.get("typeName")
        warn.allow_value = warn_data.get("allowValue")
        warn.danger_value = warn_data.get("dangerValue")
        db.session.commit()
        return {
            'status': 'success',
            'message': '更新项目warningConfig成功'
        }
    else:
        return {
            'status': 'fail',
            'message': '没有找到warning'
        }


def delWarning(id):
    Warn = WarningConfig.query.get(id)
    if Warn:
        db.session.delete(Warn)
        db.session.commit()
        return {
            'status': 'success',
            'message': 'Warn删除成功'
        }
    else:
        return {
            'status': 'fail',
            'message': 'Warn不存在'
        }
