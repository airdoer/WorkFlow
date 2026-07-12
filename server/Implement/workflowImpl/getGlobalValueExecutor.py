"""
GetGlobalValueExecutor — 从 Redis 读取全局键值

输入: key (string)
输出: success (bool), value (string)
"""
import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)

WF_PREFIX = "wf:global:"


class GetGlobalValueExecutor(BaseNodeExecutor):
    type = "getglobalvalue"

    def execute(self, config: dict, input_data: dict) -> dict:
        key = input_data.get("key") or config.get("key", "")

        key = str(key).strip()

        if not key:
            return {"error": "Key 不能为空"}

        redis_key = f"{WF_PREFIX}{key}"

        try:
            from dbImp.redisImp import my_redis
            value = my_redis.get(redis_key)
            if value is None:
                logger.info("[GetGlobalValue] Key not found: %s", redis_key)
                return {"success": False, "value": None, "error": f"Key '{key}' 不存在"}
            logger.info("[GetGlobalValue] GET %s = %s (len=%d)", redis_key, value[:50], len(value))
            return {"success": True, "value": value, "key": key}
        except Exception as e:
            logger.exception("[GetGlobalValue] Redis error: %s", e)
            return {"success": False, "value": None, "error": str(e)}
