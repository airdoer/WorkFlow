# -*- coding: utf-8 -*-
"""
Jenkins 配置文件
存储各项目的 Jenkins URL 和 Job 配置
"""

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
