# -*- coding: utf-8 -*-
"""
Jenkins 客户端封装
提供触发 Jenkins Job 的接口
"""

import requests
import json
import os
from .jenkins_config import JENKINS_AUTH, JENKINS_JOB_MAP


class JenkinsClient:
    """Jenkins 客户端类，用于触发各种 Jenkins Job"""
    
    def __init__(self, logger=None):
        """
        初始化 Jenkins 客户端
        
        Args:
            logger: 日志记录器（可选）
        """
        self.logger = logger
        self._c7_server_data = None
    
    def _load_c7_server_data(self):
        """加载 C7 服务器配置数据"""
        if self._c7_server_data is None:
            try:
                # 获取项目根目录下的 c7Server.json 文件路径
                current_dir = os.path.dirname(os.path.abspath(__file__))
                json_path = os.path.join(current_dir, '..', '..', 'data', 'C7', 'c7Server.json')
                json_path = os.path.normpath(json_path)
                
                with open(json_path, 'r', encoding='utf-8') as f:
                    self._c7_server_data = json.load(f)
                    self._log_info(f"[Jenkins] Loaded c7Server.json with {len(self._c7_server_data)} servers")
            except Exception as e:
                self._log_error(f"[Jenkins] Failed to load c7Server.json: {e}")
                self._c7_server_data = {}
        return self._c7_server_data
    
    def _get_server_env(self, namespace):
        """
        获取服务器的 env 类型
        
        Args:
            namespace: 服务器命名空间
            
        Returns:
            str: 'staging' 或 'idc'，找不到返回 None
        """
        server_data = self._load_c7_server_data()
        server_info = server_data.get(namespace)
        if server_info:
            return server_info.get('env')
        return None
    
    def _log_info(self, message):
        """记录 info 日志"""
        if self.logger:
            self.logger.info(message)
    
    def _log_warning(self, message):
        """记录 warning 日志"""
        if self.logger:
            self.logger.warning(message)
    
    def _log_error(self, message):
        """记录 error 日志"""
        if self.logger:
            self.logger.error(message)
    
    def trigger_generate_hotfix(self, project_code, revision):
        """
        触发生成 Hotfix 的 Jenkins Job
        
        Args:
            project_code: 项目代码，如 'C7'
            revision: P4 Revision 号
            
        Returns:
            bool: 成功返回 True，失败返回 False
        """
        params = {"P4REVERSION": revision}
        project_conf = JENKINS_JOB_MAP.get(project_code, {})
        jenkins_url = project_conf.get("staging_url")  # 生成hotfix使用staging
        job_name = project_conf.get("generate_hotfix", {}).get("job_name")
        
        if not jenkins_url or not job_name:
            self._log_warning(f"[Jenkins] Missing url or job_name for {project_code}.generate_hotfix, skip.")
            return False
        
        url = f"{jenkins_url}/job/{job_name}/buildWithParameters"
        self._log_info(f"[Jenkins] Trigger generate_hotfix: {url}, params: {params}")
        
        try:
            response = requests.post(url, data=params, auth=JENKINS_AUTH, timeout=10)
            if response and response.status_code in [200, 201]:
                self._log_info(f"[Jenkins] generate_hotfix triggered: {params}")
                return True
            else:
                status = response.status_code if response else "No response"
                self._log_error(f"[Jenkins] generate_hotfix FAILED: params={params}, status: {status}")
                return False
        except Exception as e:
            self._log_error(f"[Jenkins] generate_hotfix exception: params={params}, error: {e}")
            return False
    
    def trigger_reload_server(self, project_code, changelist_id, namespaces=None, groups=None, 
                             hotfix_types=None, deploy_mode=None):
        """
        触发重载服务器的 Jenkins Job
        
        Args:
            project_code: 项目代码，如 'C7'
            changelist_id: Changelist ID
            namespaces: 服务器命名空间列表或单个命名空间字符串
            groups: 服务器组列表或单个组字符串 (仅IDC环境支持)
            hotfix_types: Hotfix类型列表，如 ['lua', 'excel', 'crates']
            deploy_mode: 部署模式，'namespace' 或 'group' (仅IDC环境需要)
            
        Returns:
            dict: {
                'success': bool,
                'env': 'staging' | 'idc' | None,
                'message': str,
                'jenkins_url': str (成功时返回Jenkins构建URL)
            }
        """
        # 将单个namespace转换为列表
        if isinstance(namespaces, str):
            namespaces = [namespaces] if namespaces else []
        elif namespaces is None:
            namespaces = []
        
        # 将单个group转换为列表
        if isinstance(groups, str):
            groups = [groups] if groups else []
        elif groups is None:
            groups = []
        
        # 确定部署目标
        if not namespaces and not groups:
            return {
                'success': False,
                'env': None,
                'message': 'No namespaces or groups provided',
                'jenkins_url': None
            }
        
        # 如果提供了namespace，根据namespace检测env类型
        if namespaces:
            env_types = set()
            for namespace in namespaces:
                env = self._get_server_env(namespace)
                if env:
                    env_types.add(env)
                else:
                    self._log_warning(f"[Jenkins] Unknown namespace: {namespace}")
            
            # 检查env冲突
            if len(env_types) > 1:
                return {
                    'success': False,
                    'env': None,
                    'message': f'环境冲突: 选择的服务器包含不同的环境类型 ({", ".join(sorted(env_types))})',
                    'jenkins_url': None
                }
            
            if not env_types:
                return {
                    'success': False,
                    'env': None,
                    'message': '无法确定服务器环境类型',
                    'jenkins_url': None
                }
            
            env = list(env_types)[0]
        else:
            # 如果只提供了group，默认认为是IDC环境
            env = 'idc'
        
        # 根据env类型选择Jenkins配置
        project_conf = JENKINS_JOB_MAP.get(project_code, {})
        job_key = "reload_server"
        
        if env == "idc":
            jenkins_url = project_conf.get("idc_url")
            jenkins_web_url = project_conf.get("idc_web_url")
            job_name = project_conf.get(job_key, {}).get("idc_job_name", "Reload_Cloud_Weekly")
            env_label = "线上(IDC)"
        else:  # staging
            jenkins_url = project_conf.get("staging_url")
            jenkins_web_url = project_conf.get("staging_web_url")
            job_name = project_conf.get(job_key, {}).get("staging_job_name", "Reload_Server_Weekly")
            env_label = "内部(Staging)"
        
        if not jenkins_url or not job_name:
            return {
                'success': False,
                'env': env,
                'message': f'Missing Jenkins URL or job name for {env}',
                'jenkins_url': None
            }
        
        # 构建参数
        params = {
            "ChangelistID": changelist_id,
        }
        
        # 添加HOTFIX_TYPES参数
        # 如果是列表，直接传递列表让requests生成多个同名参数（HOTFIX_TYPES=server&HOTFIX_TYPES=client）
        # 如果是字符串，直接使用
        if hotfix_types:
            params["HOTFIX_TYPES"] = hotfix_types  # 保持原始格式（列表或字符串）
        
        # IDC环境需要额外的参数
        if env == "idc":
            # DEPLOY_MODE: namespace 或 group
            if deploy_mode:
                params["DEPLOY_MODE"] = deploy_mode
            elif namespaces and not groups:
                params["DEPLOY_MODE"] = "namespace"
            elif groups and not namespaces:
                params["DEPLOY_MODE"] = "group"
            else:
                params["DEPLOY_MODE"] = "namespace"  # 默认使用namespace模式
            
            # 根据部署模式设置对应的参数
            if params["DEPLOY_MODE"] == "namespace" and namespaces:
                params["SERVER_DEPLOY_NAMESPACE"] = ','.join(namespaces)
            elif params["DEPLOY_MODE"] == "group" and groups:
                params["SERVER_DEPLOY_GROUP"] = ','.join(groups)
            else:
                return {
                    'success': False,
                    'env': env,
                    'message': f'部署模式 {params["DEPLOY_MODE"]} 缺少对应的目标参数',
                    'jenkins_url': None
                }
        else:
            # Staging环境只需要namespace
            if namespaces:
                params["SERVER_DEPLOY_NAMESPACE"] = ','.join(namespaces)
            else:
                return {
                    'success': False,
                    'env': env,
                    'message': 'Staging环境需要提供namespace参数',
                    'jenkins_url': None
                }
        
        url = f"{jenkins_url}/job/{job_name}/buildWithParameters"
        self._log_info(f"[Jenkins] Trigger reload_server ({env_label}): {url}")
        self._log_info(f"[Jenkins] Request params: {params}")
        self._log_info(f"[Jenkins] HOTFIX_TYPES detail: type={type(params.get('HOTFIX_TYPES'))}, value='{params.get('HOTFIX_TYPES')}', repr={repr(params.get('HOTFIX_TYPES'))}")
        
        try:
            # 使用POST data方式传递参数
            # 如果HOTFIX_TYPES是列表，requests会自动生成多个同名参数
            response = requests.post(url, data=params, auth=JENKINS_AUTH, timeout=10)
            
            self._log_info(f"[Jenkins] Response status: {response.status_code}")
            self._log_info(f"[Jenkins] Response headers: {dict(response.headers)}")
            self._log_info(f"[Jenkins] Final request URL: {response.request.url}")
            self._log_info(f"[Jenkins] Request body: {response.request.body}")
            
            if response.status_code in [200, 201]:
                target_desc = params.get("SERVER_DEPLOY_NAMESPACE") or params.get("SERVER_DEPLOY_GROUP", "")
                self._log_info(f"[Jenkins] Reload server triggered ({env_label}): changelist={changelist_id}, target={target_desc}")
                
                # 构建Jenkins Job主页面URL（使用外部访问地址）
                # 如果有web_url配置，使用web_url；否则降级使用jenkins_url
                web_base_url = jenkins_web_url if jenkins_web_url else jenkins_url
                job_url = f"{web_base_url}/view/Server/job/{job_name}/"
                
                return {
                    'success': True,
                    'env': env,
                    'message': f'成功触发 {env_label} Jenkins Job',
                    'jenkins_url': job_url
                }
            else:
                status = response.status_code
                self._log_error(f"[Jenkins] Reload server FAILED ({env_label}): status={status}")
                self._log_error(f"[Jenkins] Response text: {response.text[:500] if response.text else 'Empty'}")
                return {
                    'success': False,
                    'env': env,
                    'message': f'Jenkins请求失败: HTTP {status}',
                    'jenkins_url': None
                }
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self._log_error(f"[Jenkins] Reload server exception ({env_label}): error={e}")
            self._log_error(f"[Jenkins] Traceback: {tb}")
            return {
                'success': False,
                'env': env,
                'message': f'Jenkins请求异常: {str(e)}',
                'jenkins_url': None
            }
