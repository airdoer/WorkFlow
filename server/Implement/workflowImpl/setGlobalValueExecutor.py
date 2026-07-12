"""
SetGlobalValueExecutor — 向 Redis 写入全局键值对

Redis 数据模型:
  - wf:gvar:{key}         → 实际值
  - wf:gvar:__registry__  → Hash, field=key, value=JSON {"updated_at": "ISO8601"}
"""
import json
import logging
from datetime import datetime, timezone

from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)

# Redis key prefix — short & unique to avoid collisions with other services
WF_GVAR_PREFIX = "wf:gvar:"
WF_GVAR_REGISTRY = "wf:gvar:__registry__"


class SetGlobalValueExecutor(BaseNodeExecutor):
    type = "setglobalvalue"

    def execute(self, config: dict, input_data: dict) -> dict:
        key = input_data.get("key") or config.get("key", "")
        value = input_data.get("value") or config.get("value", "")

        key = str(key).strip()
        value = str(value) if value is not None else ""

        if not key:
            return {"error": "Key 不能为空"}

        redis_key = f"{WF_GVAR_PREFIX}{key}"

        try:
            from dbImp.redisImp import my_redis
            now = datetime.now(timezone.utc).isoformat()
            pipe = my_redis.pipeline()
            pipe.set(redis_key, value)
            pipe.hset(WF_GVAR_REGISTRY, key, json.dumps({"updated_at": now}))
            pipe.execute()
            logger.info("[SetGlobalValue] SET %s (len=%d) at %s", redis_key, len(value), now)
            return {"success": True, "key": key}
        except Exception as e:
            logger.exception("[SetGlobalValue] Redis error: %s", e)
            return {"success": False, "error": str(e)}
