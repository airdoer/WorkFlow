import json
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
from Implement.kdipImpl.kdipImp import KdipClient, KdipError
from Implement.kdipImpl.kdip_config import KDIP_CMD_WHITELIST


class JenkinsExecutor(BaseNodeExecutor):
    type = "kdip"

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = KdipClient()
        return self._client

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        KDIP 节点：在 C7 服务器上执行 KDIP 任务。

        输入（连线优先，其次 config）:
          - serverName: 服务器名（namespace 或 tag key）
          - username:   用户名（可通过连线从 String 节点获取，也可手写）
          - cmdKey:     任务名（KDIP 指令 key），从下拉框选择
          - cmdParam:   附加参数（可选，JSON 字符串）

        输出:
          - success: bool — 执行成功与否
          - result:  any  — 执行结果内容（成功时为 KDIP 响应，失败时为错误信息）
        """
        # 连线输入优先，其次 config
        server_name = input_data.get('serverName') or config.get('serverName', '')
        username = input_data.get('username') or config.get('username', '')
        cmd_key = config.get('cmdKey', '')
        cmd_param_raw = config.get('cmdParam', '')

        if not server_name:
            raise ValueError("serverName 不能为空")
        if not cmd_key:
            raise ValueError("cmdKey（任务名）不能为空")
        if not username:
            raise ValueError("username 不能为空")

        # 解析 cmdParam（如果是 JSON 字符串则解析，否则当字典用）
        cmd_param = {}
        if cmd_param_raw:
            if isinstance(cmd_param_raw, str):
                try:
                    cmd_param = json.loads(cmd_param_raw)
                except Exception:
                    cmd_param = {}
            elif isinstance(cmd_param_raw, dict):
                cmd_param = cmd_param_raw

        client = self._get_client()

        try:
            # 通过 server_name 查找 zone_id 和 server_id
            server_info = client.get_server_info(server_name)
            zone_id = server_info.get('zone_id')
            server_id = server_info.get('server_id')

            result = client.extend_cmd(
                zone_id=zone_id,
                server_id=server_id,
                cmd_key=cmd_key,
                cmd_param=cmd_param,
                username=username,
            )
            return {
                'success': True,
                'result': result,
            }
        except KdipError as e:
            return {
                'success': False,
                'result': str(e),
            }
        except Exception as e:
            return {
                'success': False,
                'result': f"执行异常: {str(e)}",
            }
