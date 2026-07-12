"""
GetGlobalValueExecutor — 从 Redis 读取全局键值

读取时同步更新 registry 的 updated_at（记录最后读取时间）。
"""
import json
import logging
from datetime import datetime, timezone

from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)

WF_GVAR_PREFIX = "wf:gvar:"
WF_GVAR_REGISTRY = "wf:gvar:__registry__"


class GetGlobalValueExecutor(BaseNodeExecutor):
    type = "getglobalvalue"

    def execute(self, config: dict, input_data: dict) -> dict:
        key = input_data.get("key") or config.get("key", "")

        key = str(key).strip()

        if not key:
            return {"error": "Key 不能为空"}

        redis_key = f"{WF_GVAR_PREFIX}{key}"

        try:
            from dbImp.redisImp import my_redis
            value = my_redis.get(redis_key)
            if value is None:
                logger.info("[GetGlobalValue] Key not found: %s", redis_key)
                return {"success": False, "value": None, "error": f"Key '{key}' 不存在"}
            # 更新 registry 中的 updated_at
            now = datetime.now(timezone.utc).isoformat()
            my_redis.hset(WF_GVAR_REGISTRY, key, json.dumps({"updated_at": now}))
            logger.info("[GetGlobalValue] GET %s = %s (len=%d)", redis_key, value[:50], len(value))
            return {"success": True, "value": value, "key": key}
        except Exception as e:
            logger.exception("[GetGlobalValue] Redis error: %s", e)
            return {"success": False, "value": None, "error": str(e)}
