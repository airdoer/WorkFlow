"""
SetGlobalValueExecutor — 向 Redis 写入全局键值对

输入: key (string), value (string)
输出: success (bool)
"""
import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)

# Redis key prefix to avoid collisions with other data
WF_PREFIX = "wf:global:"


class SetGlobalValueExecutor(BaseNodeExecutor):
    type = "setglobalvalue"

    def execute(self, config: dict, input_data: dict) -> dict:
        key = input_data.get("key") or config.get("key", "")
        value = input_data.get("value") or config.get("value", "")

        key = str(key).strip()
        value = str(value) if value is not None else ""

        if not key:
            return {"error": "Key 不能为空"}

        redis_key = f"{WF_PREFIX}{key}"

        try:
            from dbImp.redisImp import my_redis
            my_redis.set(redis_key, value)
            logger.info("[SetGlobalValue] SET %s = %s (len=%d)", redis_key, value[:50] if value else "", len(value))
            return {"success": True, "key": key}
        except Exception as e:
            logger.exception("[SetGlobalValue] Redis error: %s", e)
            return {"success": False, "error": str(e)}
