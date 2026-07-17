"""
JenkinsDeploy 节点执行器 — 根据级联选择触发对应的 Jenkins Job。

级联逻辑：
  branch (mainline/preonline) × op (pack/hotfix) × env (prod/dev) × cross (no/cross)
  → 确定 job_name → 构建参数 → POST buildWithParameters

API: 复用 hotfixImpl/jenkinsImp.py 的 JenkinsClient
"""

import logging
import requests
from Implement.hotfixImpl.jenkinsImp import JenkinsClient
from Implement.hotfixImpl.jenkins_config import JENKINS_AUTH, JENKINS_JOB_MAP
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)

_jenkins_client = JenkinsClient(logger)

# ── Job 映射：key = branch_op_env[_cross] ──────────────────────────────────
JOB_MAP = {
    # 打包 - Mainline
    'mainline_pack_prod_no':      {'job_name': 'Mainline_PublicServer_C7Deploy',       'web_path': '/job/Mainline_PublicServer_C7Deploy/'},
    'mainline_pack_dev_no':       {'job_name': 'Deploy_Local_Mainline',                'web_path': '/view/Server/job/Deploy_Local_Mainline/'},
    'mainline_pack_dev_cross':    {'job_name': 'Deploy_Local_Machine_Cross',           'web_path': '/job/Deploy_Local_Machine_Cross/'},
    # 打包 - Preonline
    'preonline_pack_prod_no':     {'job_name': 'Preonline_PublicServer_C7Deploy',      'web_path': '/job/Preonline_PublicServer_C7Deploy/'},
    'preonline_pack_dev_no':      {'job_name': 'Deploy_Local_Preonline',               'web_path': '/job/Deploy_Local_Preonline/'},
    'preonline_pack_dev_cross':   {'job_name': 'Deploy_Local_Machine_Cross_Preonline', 'web_path': '/job/Deploy_Local_Machine_Cross_Preonline/'},
    # 热更 - Preonline only
    'preonline_hotfix_prod':      {'job_name': 'Reload_Cloud_Preonline',               'web_path': '/job/Reload_Cloud_Preonline/'},
    'preonline_hotfix_dev':       {'job_name': 'Preonline_GenerateHotfix',             'web_path': '/job/Preonline_GenerateHotfix/'},
}


def _get_job_key(branch: str, op: str, env: str, cross: str) -> str | None:
    """根据级联选择生成 job key"""
    if op == 'hotfix':
        if branch != 'preonline':
            return None
        return f'{branch}_hotfix_{env}'
    # 打包
    if env == 'prod':
        return f'{branch}_pack_prod_no'
    return f'{branch}_pack_dev_{cross}'


class JenkinsDeployExecutor(BaseNodeExecutor):
    type = "jenkinsdeploy"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        执行 Jenkins 部署触发。

        config 字段：
        - branch: mainline / preonline
        - op: pack / hotfix
        - env: prod / dev
        - cross: no / cross (仅打包+开发环境)
        - changelistID: 版本号（必填，可由连线提供）
        - serverName: 目标服务器（必填，可由连线提供）
        - serverGroup: 服务器组（热更+线上+group模式）
        - HOTFIX_TYPES: 热更类型列表
        - DEPLOY_MODE: namespace / group（热更+线上）
        - trigger_seal: bool
        - with_server_appendix: bool
        - CLEAN_ALL_DB_DATA: bool
        - SERVER_BUILD_TYPE: full / script / lua
        """
        # 级联选择参数
        branch = config.get('branch', '')
        op = config.get('op', '')
        env = config.get('env', '')
        cross = config.get('cross', 'no')

        if not branch or not op or not env:
            return {"success": False, "error": "请先选择分支、操作和环境"}

        job_key = _get_job_key(branch, op, env, cross)
        if not job_key or job_key not in JOB_MAP:
            return {"success": False, "error": f"无效的组合: {branch}/{op}/{env}/{cross}"}

        job_info = JOB_MAP[job_key]
        job_name = job_info['job_name']

        # 必填参数：连线值优先
        changelist_id = input_data.get('changelistID', '') or config.get('changelistID', '')
        server_name = input_data.get('serverName', '') or config.get('serverName', '')

        if not changelist_id:
            return {"success": False, "error": "ChangelistID（版本号）不能为空"}

        # 构建 Jenkins 参数
        params = {"ChangelistID": changelist_id}

        # --- 打包任务的参数 ---
        if op == 'pack':
            if not server_name:
                return {"success": False, "error": "serverName（目标服务器）不能为空"}
            params["SERVER_DEPLOY_NAMESPACE"] = server_name

            # 布尔参数
            if config.get('trigger_seal'):
                params["trigger_seal"] = "true"
            if config.get('with_server_appendix'):
                params["with_server_appendix"] = "true"
            if config.get('CLEAN_ALL_DB_DATA'):
                params["CLEAN_ALL_DB_DATA"] = "true"

            # 更新模式
            build_type = config.get('SERVER_BUILD_TYPE', 'full')
            if build_type:
                params["SERVER_BUILD_TYPE"] = build_type

        # --- 热更任务的参数 ---
        elif op == 'hotfix':
            hotfix_types = config.get('HOTFIX_TYPES', [])
            if isinstance(hotfix_types, str):
                hotfix_types = [hotfix_types]
            if not hotfix_types:
                return {"success": False, "error": "HOTFIX_TYPES（热更类型）不能为空"}

            if env == 'prod':
                # 线上热更：需要 DEPLOY_MODE
                deploy_mode = config.get('DEPLOY_MODE', 'namespace')
                params["DEPLOY_MODE"] = deploy_mode
                params["HOTFIX_TYPES"] = hotfix_types  # 列表，requests 自动多值

                if deploy_mode == 'namespace':
                    if not server_name:
                        return {"success": False, "error": "namespace 模式需要选择目标服务器"}
                    params["SERVER_DEPLOY_NAMESPACE"] = server_name
                elif deploy_mode == 'group':
                    server_group = input_data.get('serverGroup', '') or config.get('serverGroup', '')
                    if not server_group:
                        return {"success": False, "error": "group 模式需要选择服务器组"}
                    params["SERVER_DEPLOY_GROUP"] = server_group
            else:
                # 开发环境热更
                if not server_name:
                    return {"success": False, "error": "serverName（目标服务器）不能为空"}
                params["SERVER_DEPLOY_NAMESPACE"] = server_name
                params["HOTFIX_TYPES"] = hotfix_types

        # 获取 Jenkins API URL
        project_conf = JENKINS_JOB_MAP.get('C7', {})
        jenkins_url = project_conf.get('staging_url')  # API 地址（内部代理）
        web_base_url = project_conf.get('staging_web_url', 'https://game-hangzhou-jenkinsc7.test.gifshow.com')

        if not jenkins_url:
            return {"success": False, "error": "Jenkins API URL 未配置 (JENKINS_JOB_MAP.C7.staging_url)"}

        trigger_url = f"{jenkins_url}/job/{job_name}/buildWithParameters"
        job_web_url = f"{web_base_url}{job_info['web_path']}"

        logger.info("[JenkinsDeploy] job_key=%s, job=%s, params=%s", job_key, job_name, params)
        logger.info("[JenkinsDeploy] trigger_url=%s", trigger_url)

        # 触发 Jenkins Job
        try:
            response = requests.post(trigger_url, data=params, auth=JENKINS_AUTH, timeout=15)
        except requests.exceptions.RequestException as e:
            logger.error("[JenkinsDeploy] Request failed: %s", e)
            return {"success": False, "error": f"Jenkins 请求失败: {e}"}

        if response.status_code in [200, 201]:
            # 从 Location header 获取队列 URL，提取 build number
            queue_url = response.headers.get('Location', '')
            build_number = ''
            if queue_url:
                # 如 http://jenkins/queue/item/123/
                parts = queue_url.rstrip('/').split('/')
                if parts:
                    build_number = parts[-1]

            logger.info("[JenkinsDeploy] Job triggered: %s, queue=%s", job_name, queue_url)
            return {
                "success": True,
                "jobUrl": job_web_url,
                "buildNumber": build_number or "pending",
                "job_name": job_name,
                "params": {k: v for k, v in params.items() if k != 'ChangelistID'},
            }
        else:
            status = response.status_code
            error_text = response.text[:500] if response.text else 'Empty'
            logger.error("[JenkinsDeploy] FAILED: status=%s, body=%s", status, error_text)
            return {
                "success": False,
                "error": f"Jenkins 请求失败: HTTP {status}",
            }
