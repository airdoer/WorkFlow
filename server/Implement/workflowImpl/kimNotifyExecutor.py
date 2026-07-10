from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
from Implement.hotfixImpl.c7KimRobot import C7KimRobot


class KimNotifyExecutor(BaseNodeExecutor):
    type = "kimnotify"

    def __init__(self):
        self._robot = None

    def _get_robot(self):
        if self._robot is None:
            self._robot = C7KimRobot()
        return self._robot

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        KimNotify 节点：通过 Kim 机器人发送消息。

        输入（username 和 groupId 二选一）:
          - username: 用户名（连线或 config），发送给指定用户
          - groupId: 群组 ID（连线或 config），发送给指定群
          - message: 消息内容（连线或 config）

        输出:
          - success: bool — 发送成功与否
          - message: str  — 结果或错误信息
        """
        # 优先从连线 input_data 获取，其次从 config
        username = input_data.get('username') or config.get('username', '')
        group_id = input_data.get('groupId') or config.get('groupId', '')
        message = input_data.get('message') or config.get('message', '')

        if not message:
            raise ValueError("message 消息内容不能为空")
        if not username and not group_id:
            raise ValueError("username 和 groupId 至少填写一个")

        robot = self._get_robot()

        if username:
            ok, err = robot.send_msg_to_user(username, message)
        else:
            ok, err = robot.send_msg_to_group(group_id, message)

        return {
            'success': ok,
            'message': '' if ok else err,
        }
