# -*- coding: utf-8 -*-
"""
照搬 ue-ci-code/scripts/common/tools_c7_kim_robot.py 的实现。
仅做必要适配：
  1) 新增类别名 C7KimRobot（hotfixTool.py 已用此名 import）；
  2) 新增 send_msg_to_user / send_msg_to_group 便捷封装，签名 (username, msg)，
     供 _detect_and_notify_conflicts 调用且返回 (ok, err)。
其余实现与 ue-ci-code 完全一致。
"""
import os
import sys
import requests

sys.path.append(os.getcwd())

"""
    send_type：可以为username和groupId
    如果是groupID，需要机器人在群里
"""


class ToolsC7KimRobot(object):
    def __init__(self):
        # robot 地址：允许通过环境变量 KIM_ROBOT_URL 覆盖（用于走端口转发器）
        self.robot_url = os.environ.get("KIM_ROBOT_URL") or "http://172.28.212.159:5000"
        self.api_paths = {
            "send_msg": "/openapi_transfer/send_msg",
            "send_file": "/openapi_transfer/send_file",
            "invite_bot_to_group": "/openapi_transfer/invite_bot_to_group",
            "send_image": "/openapi_transfer/send_image",
            "invite_user": "/openapi_transfer/invite_user_to_group"
        }
        # 代理：默认禁用所有代理（强制直连 robot，避开系统级 HTTP_PROXY 拐到错误出口）
        # 如需显式走代理，设置环境变量 KIM_ROBOT_PROXY="http://x.x.x.x:port"
        proxy = os.environ.get("KIM_ROBOT_PROXY")
        if proxy:
            self._proxies = {"http": proxy, "https": proxy}
        else:
            # None 表示不走任何代理（包括系统 HTTP_PROXY/HTTPS_PROXY）
            self._proxies = {"http": None, "https": None}

    def _request_kwargs(self):
        # proxies 始终显式传递，避免 requests 通过 trust_env 读取系统 HTTP_PROXY
        return {"timeout": 5, "proxies": self._proxies}

    def send_msg(self, send_type, send_id, msg):
        api_path_type = "send_msg"
        url = self.robot_url + self.api_paths[api_path_type]
        params = {
            'send_type': send_type,
            'send_id': send_id,
            'msg': msg
        }
        result = requests.post(url, json=params, **self._request_kwargs())
        # 让上层能感知到 4xx/5xx：直接抛错
        if not result.ok:
            raise requests.HTTPError(
                f"kim robot http {result.status_code}: {result.text[:200]}"
            )
        return result

    def send_file(self, send_type, send_id, file_path, new_file_name=None):
        api_path_type = "send_file"
        url = self.robot_url + self.api_paths[api_path_type]
        file_name = os.path.basename(file_path)
        files = {
            'file': (file_name if new_file_name is None else new_file_name, open(file_path, 'rb'))
        }
        params = {
            'send_type': send_type,
            'send_id': send_id
        }
        result = requests.post(url, data=params, files=files)

    def invite_bot_to_group(self, group_id, group_master):
        api_path_type = "invite_bot_to_group"
        url = self.robot_url + self.api_paths[api_path_type]
        params = {
            'group_id': group_id,
            'group_master': group_master
        }
        result = requests.post(url, json=params)

    def send_image(self, send_type, send_id, file_path, new_file_name=None):
        api_path_type = "send_image"
        url = self.robot_url + self.api_paths[api_path_type]
        file_name = os.path.basename(file_path)
        files = {
            'file': (file_name if new_file_name is None else new_file_name, open(file_path, 'rb'))
        }
        params = {
            'send_type': send_type,
            'send_id': send_id
        }
        result = requests.post(url, data=params, files=files)

    def invite_user(self, group_id, member_usernames):
        api_path_type = "invite_user"
        url = self.robot_url + self.api_paths[api_path_type]
        params = {
            'group_id': group_id,
            'member_usernames': member_usernames
        }
        result = requests.post(url, json=params)
        print(result)


# ============================================================================
# 适配层：保持 hotfixTool.py 的调用接口不变
# ----------------------------------------------------------------------------
# hotfixTool.py 里写的是：
#     from Implement.hotfixImpl.c7KimRobot import C7KimRobot
#     kim_robot = C7KimRobot()
#     ok, err = kim_robot.send_msg_to_user(username, msg)
# 这里：
#   1) 把 C7KimRobot 作为 ToolsC7KimRobot 的别名（完全一致的实现）；
#   2) 给它加 send_msg_to_user/send_msg_to_group 封装，返回 (ok, err)。
# ============================================================================

class C7KimRobot(ToolsC7KimRobot):
    """C7 Kim 机器人客户端，行为与 ToolsC7KimRobot 完全一致，仅扩展便捷封装。"""

    def send_msg_to_user(self, username, msg):
        try:
            self.send_msg('username', username, msg)
            return True, ''
        except Exception as e:
            return False, str(e)

    def send_msg_to_group(self, group_id, msg):
        try:
            self.send_msg('groupId', group_id, msg)
            return True, ''
        except Exception as e:
            return False, str(e)


if __name__ == "__main__":
    tools_kim = ToolsC7KimRobot()
    tools_kim.invite_user('5106961315438619', ['mengyun03', 'matengfei'])
