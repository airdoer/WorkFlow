# heatmap 相关的route

# builtin
import os
import time

# 3rd ext
from flask import request, jsonify, url_for
from flask.views import MethodView

# int
from appImp import app
from dbImp import HeatMap_mysqllmp as Hm_mysql
from actions import HeatMapAction
from models.heatmap import WarningConfig

# region init
# endregion


# region route
class ProjectApi(MethodView):
    def get(self, p_code):
        if not p_code:
            projects = Hm_mysql.getAllProject()
            if projects:
                projects = [project.ProjectConfigToDict() for project in projects]
                for i, project in enumerate(projects):
                    code = project["projectName"]
                    warns = Hm_mysql.getAllWaringByPcode(code)
                    warns = [warn.WarningConfigToDict() for warn in warns]
                    projects[i]["typeList"] = warns

                return jsonify({
                    'status': 'success',
                    'pageSize': 10,
                    'pageNo': 1,
                    'totalCount': 2,
                    'totalPage': 1,
                    'data': projects
                })
            else:
                return jsonify({
                    'status': 'fail',
                    'pageSize': 10,
                    'pageNo': 1,
                    'totalCount': 2,
                    'totalPage': 1,
                    'data': []
                })
        else:
            project = Hm_mysql.getProject(p_code)
            if project:
                result = project.ProjectConfigToDict()
                return jsonify({
                    'status': 'success',
                    'result': result
                })
            else:
                return {
                    'status': 'fail',
                    'message': '没有projectName'
                }

    def post(self):
        project_data = request.json
        if project_data.get("projectName"):
            result = Hm_mysql.addProject(project_data)
            # show_items = request.json.get("show_items")
            # show_items = str(show_items).split(",")
            # for show_item in show_items:
            #     if show_item:
            #         warn_data = dict()
            #         warn_data['p_code'] = project_data.get("p_code")
            #         warn_data['key'] = show_item
            #         Hm_mysql.addWarning(warn_data)
            return jsonify(result)
        return "project post return"

    def delete(self, p_code):
        result = Hm_mysql.delProject(p_code)
        return jsonify(result)

    # def put(self, p_code):
    #     project_data = request.json
    #     if p_code and project_data.get("show_items"):
    #         result = Hm_mysql.upProjectByShow(project_data)
    #         return jsonify(result)
    #     else:
    #         return {
    #             'status': 'fail',
    #             'message': '没有show_items'
    #         }


project_view = ProjectApi.as_view('project_api')
app.add_url_rule('/project/', view_func=project_view, methods=['POST'])
app.add_url_rule('/project/', view_func=project_view, methods=['GET'], defaults={'p_code': None})
app.add_url_rule('/project/<string:p_code>', view_func=project_view, methods=['GET', 'DELETE'])


class SceneApi(MethodView):
    def get(self, scene_id):
        scene_id = request.args.get("sceneId")
        if not scene_id:
            p_code = request.args.get('projectName')
            scenes = Hm_mysql.getSceneBycode(p_code)
            if scenes:
                scenes = [scene.SceneConfigToDict() for scene in scenes]
                scenes_name = []
                for scene in scenes:
                    if scene["sceneName"] not in scenes_name:
                        scenes_name.append(scene["sceneName"])

                return jsonify({
                    'status': 'success',
                    'pageSize': 10,
                    'pageNo': 1,
                    'totalCount': 2,
                    'totalPage': 1,
                    'sceneName': scenes_name,
                    'data': scenes
                })
            else:
                return jsonify({
                    'status': 'fail',
                    'message': '没有该项目',
                    'pageSize': 10,
                    'pageNo': 1,
                    'totalCount': 2,
                    'totalPage': 1,
                    'sceneName': '',
                    'data': []
                })
        else:
            scene = Hm_mysql.getSceneByid(scene_id)
            if scene:
                scene_data = scene.SceneConfigToDict()
                scene_data_addr = scene_data["dataFile"]
                filename = 'HeatMap/image/' + scene_data["imgFile"]
                scene_img_addr = url_for('static', filename=filename)
                scene_p_code = scene_data["projectName"]
                # scene_upload_date = scene_data["uploadDate"].strftime('%Y-%m-%d %H:%M')
                # img_data = HeatMapAction.get_image_data(scene_data_addr, key)  # 返回list
                # warning = Hm_mysql.getWaring(scene_p_code, key)

                img_all_data = HeatMapAction.get_image_data(scene_data_addr)
                warns = Hm_mysql.getAllWaringByPcode(scene_p_code)

                if warns:
                    warns = [warn.WarningConfigToDict()["typeName"] for warn in warns]
                    return jsonify({
                        'status': 'success',
                        'sceneID': scene_id,
                        'data': img_all_data,
                        'imgFile': scene_img_addr,
                        'typeList': warns
                        # 'uploadDate': scene_upload_date
                    })
                else:
                    return jsonify({
                        'status': 'success',
                        'sceneID': scene_id,
                        'data': img_all_data,
                        'imgFile': scene_img_addr
                        # 'uploadDate': scene_upload_date
                    })

    def post(self):
        if request.form:
            scene_data_dict = request.form.to_dict()
            path = os.path.join(os.getcwd(), "static", "HeatMap")
            now_time = str(int(time.time()))
            if 'imgFile' in request.files:
                image = request.files["imgFile"]
                image_name = now_time + '.png'
                scene_data_dict['imgFile'] = image_name
                image_path = os.path.join(path, "image", image_name)
                image.save(image_path)
            else:
                scene_name = scene_data_dict["sceneName"]
                p_code = scene_data_dict["projectName"]
                history_image_data = Hm_mysql.getSceneImg(p_code, scene_name)
                scene_data_dict['imgFile'] = history_image_data["imgFile"]
                image_name = scene_data_dict['imgFile']
                if "leftBottom" not in scene_data_dict.keys():
                    scene_data_dict["leftBottom"] = history_image_data["leftBottom"]
                    scene_data_dict["rightTop"] = history_image_data["rightTop"]

            if 'dataFile' in request.files:
                data = request.files["dataFile"]
                data_name = now_time + '.txt'
                scene_data_dict['dataFile'] = data_name
                data_path = os.path.join(path, "data", data_name)
                data.save(data_path)
            else:
                if os.path.exists(image_path):
                    os.remove(image_path)
                return {
                    'status': 'fail',
                    'message': '没有data文件'
                }
            left_bottom = scene_data_dict["leftBottom"]
            right_top = scene_data_dict["rightTop"]
            width_min, height_min = left_bottom.split(",")
            width_max, height_max = right_top.split(",")
            y_transposition_z = scene_data_dict.get("yTOz", False)
            if y_transposition_z == "undefined":
                y_transposition_z = None
            result, error = HeatMapAction.deal_image_data(data_name, image_name, width_min,
                                                          width_max, height_min, height_max, y_transposition_z)
            if result:
                result = Hm_mysql.addScene(scene_data_dict)
            else:
                msg = '数据处理失败，请检查数据格式:' + str(error)
                result = {
                    'status': 'fail',
                    'message': msg
                }
                # 失败删除之前保留的文件
                if os.path.exists(data_path):
                    os.remove(data_path)
                if os.path.exists(image_path):
                    os.remove(image_path)
            return jsonify(result)
        else:
            return {
                'status': 'fail',
                'message': '没有scene_data'
            }

    def delete(self, scene_id):
        result = Hm_mysql.delScene(scene_id)
        return jsonify(result)


scene_view = SceneApi.as_view('scene_api')
app.add_url_rule('/scene/', view_func=scene_view, methods=['GET'], defaults={'scene_id': None})
app.add_url_rule('/scene/<string:scene_id>', view_func=scene_view, methods=['GET', 'DELETE'])
app.add_url_rule('/scene/', view_func=scene_view, methods=['POST'])


class WarningApi(MethodView):
    def get(self, p_code):
        p_code = request.args.get("projectName")
        key = request.args.get('typeName') if request.args.get('typeName') is not None else None
        if key:
            warn_data = WarningConfig.WarningConfig.query.filter_by(p_code=p_code, key=key).first()
            warn_data = warn_data.WarningConfigToDict()
            return jsonify({
                'status': 'success',
                'result': warn_data
            })
        warn_data = WarningConfig.WarningConfig.query.filter_by(p_code=p_code)
        if warn_data:
            results = [warn.WarningConfigToDict() for warn in warn_data]
            return jsonify({
                'status': 'success',
                'result': results
            })
        else:
            return {
                'status': 'fail',
                'message': '没有p_code的数据'
            }

    def post(self, p_code):
        warn_data = request.json
        result = Hm_mysql.addWarning(warn_data)
        return jsonify(result)

    def put(self, p_code):
        warn_data = request.json
        if warn_data.get("id"):
            result = Hm_mysql.upWaring(warn_data)
            return jsonify(result)
        else:
            return {
                'status': 'fail',
                'message': '没有id'
            }

    def delete(self):
        id = request.json.get("id")
        result = Hm_mysql.delWarning(id)
        return jsonify(result)


warn_view = WarningApi.as_view('warn_api')
app.add_url_rule('/warning/<string:p_code>', view_func=warn_view, methods=['GET'])
app.add_url_rule('/warning/', view_func=warn_view, methods=['POST', 'DELETE', 'PUT', "GET"], defaults={'p_code': None})

# endregion
