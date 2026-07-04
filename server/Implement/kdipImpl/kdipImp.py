# -*- coding: utf-8 -*-
"""
KDIP客户端封装
提供KDIP API调用接口
"""

import base64
import hashlib
import hmac
import json
import time
import os
from urllib.parse import urljoin

import requests

from .kdip_config import (
    KDIP_CONFIG,
    KDIP_CMD_WHITELIST,
    KDIP_CMD_COOLDOWN,
    DEFAULT_CMD_COOLDOWN,
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    TOKEN_EXPIRE_BUFFER
)


class KdipError(Exception):
    """KDIP调用异常"""
    pass


class KdipConfigError(KdipError):
    """KDIP配置异常"""
    pass


class KdipClient:
    """KDIP客户端类"""
    
    DEFAULT_TOKEN_PATH = "/oauth2/access_token"
    DEFAULT_EXTEND_CMD_PATH = "/api/gm/kdip/open/extend-cmd"
    DEFAULT_SCOPE = "game_gm"
    DEFAULT_GRANT_TYPE = "client_credentials"
    
    _token_cache = {}
    _cmd_cooldown_cache = {}  # 指令CD缓存，格式：{(namespace, cmd_key): last_execute_time}
    
    def __init__(self, config=None, timeout=DEFAULT_TIMEOUT, max_retries=DEFAULT_MAX_RETRIES, logger=None):
        """
        初始化KDIP客户端
        
        Args:
            config: KDIP配置字典（可选）
            timeout: 请求超时时间
            max_retries: 最大重试次数
            logger: 日志记录器（可选）
        """
        self.config = config or KDIP_CONFIG
        self.app_id = self.config["app_id"]
        self.app_secret = self.config["app_secret"]
        self.token_url = self.config.get("token_url")
        self.open_api_url = self.config.get("open_api_url")
        self.scope = self.config.get("scope", self.DEFAULT_SCOPE)
        self.grant_type = self.config.get("grant_type", self.DEFAULT_GRANT_TYPE)
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logger
        self._c7_server_data = None
    
    def _load_c7_server_data(self):
        """加载C7服务器配置数据"""
        if self._c7_server_data is None:
            try:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                json_path = os.path.join(current_dir, '..', '..', 'data', 'C7', 'c7Server.json')
                json_path = os.path.normpath(json_path)
                
                with open(json_path, 'r', encoding='utf-8') as f:
                    self._c7_server_data = json.load(f)
                    self._log_info(f"[KDIP] Loaded c7Server.json with {len(self._c7_server_data)} servers")
            except Exception as e:
                self._log_error(f"[KDIP] Failed to load c7Server.json: {e}")
                self._c7_server_data = {}
        return self._c7_server_data
    
    def get_server_list(self):
        """
        获取服务器列表
        
        Returns:
            list: 服务器列表
        """
        server_data = self._load_c7_server_data()
        servers = []
        for namespace, info in server_data.items():
            servers.append({
                "namespace": namespace,
                "name": info.get("name", namespace),
                "zone_id": info.get("zone_id"),
                "server_id": info.get("server_id"),
                "env": info.get("env")
            })
        return servers
    
    def get_server_info(self, namespace):
        """
        根据namespace获取服务器信息
        
        Args:
            namespace: 服务器命名空间
            
        Returns:
            dict: 服务器信息，包含zone_id和server_id
        """
        server_data = self._load_c7_server_data()
        server_info = server_data.get(namespace)
        if not server_info:
            raise KdipError(f"服务器 {namespace} 不存在")
        return {
            "zone_id": server_info.get("zone_id"),
            "server_id": server_info.get("server_id"),
            "name": server_info.get("name"),
            "env": server_info.get("env")
        }
    
    def _log_info(self, message):
        """记录info日志"""
        if self.logger:
            self.logger.info(message)
        else:
            print(f"[INFO] {message}")
    
    def _log_warning(self, message):
        """记录warning日志"""
        if self.logger:
            self.logger.warning(message)
        else:
            print(f"[WARNING] {message}")
    
    def _log_error(self, message):
        """记录error日志"""
        if self.logger:
            self.logger.error(message)
        else:
            print(f"[ERROR] {message}")
    
    @classmethod
    def clear_token_cache(cls):
        """清除token缓存"""
        cls._token_cache.clear()
    
    @classmethod
    def clear_cooldown_cache(cls):
        """清除CD缓存"""
        cls._cmd_cooldown_cache.clear()
    
    def _get_cmd_cooldown(self, cmd_key):
        """
        获取指令的CD时间
        
        Args:
            cmd_key: 指令key
            
        Returns:
            int: CD时间（秒）
        """
        return KDIP_CMD_COOLDOWN.get(cmd_key, DEFAULT_CMD_COOLDOWN)
    
    def _check_cooldown(self, namespace, cmd_key):
        """
        检查指令CD
        
        Args:
            namespace: 服务器命名空间
            cmd_key: 指令key
            
        Raises:
            KdipError: 如果还在CD中
        """
        cache_key = (namespace, cmd_key)
        last_execute_time = self._cmd_cooldown_cache.get(cache_key)
        
        if last_execute_time:
            now = time.time()
            cd_time = self._get_cmd_cooldown(cmd_key)
            elapsed = now - last_execute_time
            
            if elapsed < cd_time:
                remaining = int(cd_time - elapsed)
                raise KdipError(f"指令 {cmd_key} 冷却中，请等待 {remaining} 秒后再试")
    
    def _update_cooldown(self, namespace, cmd_key):
        """
        更新指令CD时间
        
        Args:
            namespace: 服务器命名空间
            cmd_key: 指令key
        """
        cache_key = (namespace, cmd_key)
        self._cmd_cooldown_cache[cache_key] = time.time()
    
    @staticmethod
    def compact_json(data):
        """紧凑的JSON序列化"""
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    
    def build_sign(self, request_body):
        """
        构建签名
        
        Args:
            request_body: 请求体字符串
            
        Returns:
            str: Base64编码的签名
        """
        sign = hmac.new(
            self.app_secret.encode("utf-8"),
            request_body.encode("utf-8"),
            hashlib.sha256
        ).digest()
        return base64.b64encode(sign).decode("utf-8")
    
    def get_access_token(self):
        """
        获取access token（带缓存）
        
        Returns:
            str: access token
        """
        cache_key = self.app_id
        cached_token = self._token_cache.get(cache_key)
        now = int(time.time())
        
        if cached_token and cached_token["expire_at"] > now:
            return cached_token["access_token"]
        
        params = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
            "grant_type": self.grant_type,
            "scope": self.scope,
        }
        
        try:
            response = requests.get(self.token_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self._log_error(f"[KDIP] access token request failed: {self.token_url}, error={str(e)}")
            raise KdipError("获取KDIP access_token失败")
        except ValueError as e:
            self._log_error(f"[KDIP] access token response is not json: {self.token_url}, error={str(e)}")
            raise KdipError("KDIP access_token响应不是JSON")
        
        access_token = data.get("access_token")
        if not access_token:
            self._log_error(f"[KDIP] access token missing, result={data.get('result')}")
            raise KdipError("KDIP access_token缺失")
        
        expires_in = int(data.get("expires_in") or 0)
        if expires_in > 0:
            expire_at = now + max(expires_in - TOKEN_EXPIRE_BUFFER, 1)
            self._token_cache[cache_key] = {
                "access_token": access_token,
                "expire_at": expire_at,
            }
        
        return access_token
    
    def extend_cmd(self, zone_id, server_id, cmd_key, cmd_param=None, username=None):
        """
        执行KDIP扩展指令
        
        Args:
            zone_id: 区服ID
            server_id: 服务器ID
            cmd_key: 指令key
            cmd_param: 指令参数（可选）
            username: 用户名
            
        Returns:
            dict: API响应结果
        """
        if not username:
            raise KdipError("KDIP username不能为空")
        if not zone_id:
            raise KdipError("KDIP zone_id不能为空")
        
        # 检查指令是否在白名单中
        if cmd_key not in KDIP_CMD_WHITELIST:
            raise KdipError(f"指令 {cmd_key} 不在白名单中")
        
        payload = {
            "zoneId": zone_id,
            "serverId": server_id,
            "cmdParam": {
                "cmd_key": cmd_key,
                "cmd_param": cmd_param or {},
            }
        }
        request_body = self.compact_json(payload)
        
        last_error = None
        for attempt in range(self.max_retries + 1):
            ts = int(time.time() * 1000)
            seqid = str(ts)
            headers = {
                "username": username,
                "access-token": self.get_access_token(),
                "app-id": self.app_id,
                "sign": self.build_sign(request_body),
                "Content-Type": "application/json",
                "seqid": seqid,
            }
            
            self._log_info(f"[KDIP] extend_cmd request: cmd_key={cmd_key}, zone_id={zone_id}, server_id={server_id}, attempt={attempt + 1}")
            
            try:
                response = requests.post(
                    self.open_api_url,
                    headers=headers,
                    data=request_body.encode("utf-8"),
                    timeout=self.timeout
                )
                response.raise_for_status()
                result = response.json()
                self._log_info(f"[KDIP] extend_cmd success: cmd_key={cmd_key}, result={result}")
                return result
            except requests.RequestException as e:
                last_error = e
                self._log_warning(
                    f"[KDIP] extend_cmd request failed: cmd_key={cmd_key}, "
                    f"server_id={server_id}, attempt={attempt + 1}, error={str(e)}"
                )
            except ValueError as e:
                self._log_error(
                    f"[KDIP] extend_cmd response is not json: cmd_key={cmd_key}, "
                    f"server_id={server_id}, error={str(e)}"
                )
                raise KdipError("KDIP响应不是JSON")
            
            if attempt < self.max_retries:
                time.sleep(1)
        
        raise KdipError(f"KDIP请求失败: {str(last_error)}")
    
    def _get_msg(self, response, cmd_key):
        """
        从响应中提取msg字段
        
        Args:
            response: API响应
            cmd_key: 指令key
            
        Returns:
            msg内容
        """
        if "msg" not in response:
            self._log_error(f"[KDIP] response missing msg: cmd_key={cmd_key}, result={response.get('result')}")
            raise KdipError("KDIP响应缺少msg")
        return response["msg"]
    
    def get_current_config(self, zone_id, server_id, username):
        """获取当前配置"""
        cmd_key = "kdip_game_get_config_for_qa"
        return self._get_msg(self.extend_cmd(zone_id, server_id, cmd_key, username=username), cmd_key)
    
    def get_switch_state(self, zone_id, server_id, username):
        """获取开关状态"""
        cmd_key = "kdip_game_get_service_switch_state"
        return self._get_msg(self.extend_cmd(
            zone_id,
            server_id,
            cmd_key,
            cmd_param={"server_id": str(server_id)},
            username=username
        ), cmd_key)
    
    def get_hotfix_info(self, zone_id, server_id, username):
        """获取hotfix信息"""
        cmd_key = "kdip_game_get_hotfix_info"
        return self._get_msg(self.extend_cmd(zone_id, server_id, cmd_key, username=username), cmd_key)
    
    def get_server_run_info(self, zone_id, server_id, username):
        """获取服务器运行信息"""
        cmd_key = "kdip_game_get_server_run_info"
        return self._get_msg(self.extend_cmd(zone_id, server_id, cmd_key, username=username), cmd_key)
    
    def get_stall_metric_info(self, zone_id, server_id, username):
        """获取交易行信息"""
        cmd_key = "kdip_game_get_stall_metric_info"
        return self._get_msg(self.extend_cmd(zone_id, server_id, cmd_key, username=username), cmd_key)
    
    def execute_custom_cmd(self, namespace, cmd_key, cmd_param, username):
        """
        执行自定义指令
        
        Args:
            namespace: 服务器命名空间
            cmd_key: 指令key
            cmd_param: 指令参数
            username: 用户名
            
        Returns:
            dict: 执行结果
        """
        # 检查CD
        self._check_cooldown(namespace, cmd_key)
        
        server_info = self.get_server_info(namespace)
        zone_id = server_info["zone_id"]
        server_id = server_info["server_id"]
        
        result = self.extend_cmd(zone_id, server_id, cmd_key, cmd_param, username)
        
        # 更新CD时间
        self._update_cooldown(namespace, cmd_key)
        
        return result
