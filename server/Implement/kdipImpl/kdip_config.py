# -*- coding: utf-8 -*-
"""
KDIP配置文件
"""

# KDIP API 配置
KDIP_CONFIG = {
    "app_id": "ks697776469461717331",
    "app_secret": "KC-VH0uJLxXqEliLwS44Jg",
    "token_url": "https://gamecloud-extranet-proxy.staging.kuaishou.com/oauth2/access_token",
    "open_api_url": "http://gamecloud-gmt.corp.kuaishou.com/ks697776469461717331/api/gm/kdip/open/extend-cmd"
}

# KDIP指令白名单
KDIP_CMD_WHITELIST = [
    "kdip_game_get_config_for_qa",
    "kdip_game_get_service_switch_state",
    "kdip_game_get_hotfix_info",
    "kdip_game_get_server_run_info",
    "kdip_game_get_stall_metric_info",
    # 可以继续添加其他允许的指令
]

# KDIP指令CD配置（秒）
# 格式：{指令key: CD时间}
# 对于同一个服务器的同一个指令，需要等待CD时间后才能再次执行
KDIP_CMD_COOLDOWN = {
    "kdip_game_get_config_for_qa": 10,
    "kdip_game_get_service_switch_state": 5,
    "kdip_game_get_hotfix_info": 5,
    "kdip_game_get_server_run_info": 5,
    "kdip_game_get_stall_metric_info": 5,
}

# 默认CD时间（秒）- 如果指令没有配置CD，使用此值
DEFAULT_CMD_COOLDOWN = 5

# 超时配置
DEFAULT_TIMEOUT = 10
DEFAULT_MAX_RETRIES = 2

# Token缓存过期缓冲时间（秒）
TOKEN_EXPIRE_BUFFER = 300
