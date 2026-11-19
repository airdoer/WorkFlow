# -*- coding: utf-8 -*-
"""
Jenkins 配置文件
存储各项目的 Jenkins URL 和 Job 配置
"""

import datetime

# Jenkins 认证信息
JENKINS_AUTH = ("chenzhixu", "11b8041f1a29349b87f33f6d7c9c69f0b8")

# Jenkins Job 配置映射
JENKINS_JOB_MAP = {
    "C7": {
        # API调用地址（内部）
        "staging_url": "http://gamecloud-api.test.gifshow.com/c7Jenkins",
        "idc_url": "http://gamecloud-api.test.gifshow.com/c7Jenkins",
        # 浏览器访问地址（外部）
        "staging_web_url": "https://game-hangzhou-jenkinsc7.test.gifshow.com",
        "idc_web_url": "https://game-hangzhou-jenkinsc7.test.gifshow.com",
        "reload_server": {
            "staging_job_name": "Reload_Server_Weekly",
            "idc_job_name": "Reload_Cloud_Weekly"
        }
    }
}


# ── PublicServer 打包任务（供本地 Skill / Web 节点共用）─────────────────────

# Jenkins 浏览器/API 根地址：用户给出的 PublicServer 打包 Job 均在此 host 下
PUBLIC_SERVER_JENKINS_URL = "https://game-hangzhou-jenkinsc7.test.gifshow.com"

# 分支 -> 打包 Job 名称（job/{job_name}/buildWithParameters）
PUBLIC_SERVER_PACK_JOB = {
    "mainline":  "Mainline_PublicServer_C7Deploy",
    "preonline": "Preonline_PublicServer_C7Deploy",
    "online":    "Online_PublicServer_C7Deploy",
}

# 主干包默认版本号；"最新包"表示版本字段留空
DEFAULT_PACK_CHANGELIST_ID = "2333201"
LATEST_VERSION_TOKEN = "latest"

# 标签发起人标识（KIM_NOTIFICATION_TAG 第一段）
NOTIFICATION_TAG_USER = "mcp"


def build_kim_notification_tag(branch: str, version: str) -> str:
    """
    生成 Jenkins 新增参数 KIM_NOTIFICATION_TAG 的值。

    格式：用户 + mcp + 日期 + 分支 + 版本（下划线连接）
    例：打主干包 CL=2333201 -> mcp_20261119_mainline_2333201
        打主干最新包         -> mcp_20261119_mainline_latest

    Args:
        branch: mainline / preonline / online
        version: ChangelistID 版本号；"latest" 表示最新包

    Returns:
        str: tag 值
    """
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    return f"{NOTIFICATION_TAG_USER}_{date_str}_{branch}_{version}"
