import logging
import json
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)

# Redis is optional — only works if redis package is installed
_redis_client = None


def _get_redis_client():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.Redis(
                host='localhost',
                port=6379,
                decode_responses=True,
                socket_timeout=5,
            )
        except ImportError:
            logger.warning("[Redis] redis package not installed")
            return None
        except Exception as e:
            logger.warning("[Redis] Connection failed: %s", e)
            return None
    return _redis_client


class RedisExecutor(BaseNodeExecutor):
    """Redis node: GET/SET/HGET/HSET/DEL/KEYS operations."""

    type = "redis"

    def execute(self, config: dict, input_data: dict) -> dict:
        command = config.get("command", "GET").upper()
        key = input_data.get("key", config.get("key", ""))
        field = input_data.get("field", config.get("field", ""))
        value = input_data.get("value", config.get("value", ""))

        if not key and command not in ("KEYS",):
            return {"error": "Redis key is required"}

        client = _get_redis_client()
        if client is None:
            return {"error": "Redis is not available (redis package not installed or connection failed)"}

        try:
            if command == "GET":
                result = client.get(key)
                if result and result.startswith("{") or result and result.startswith("["):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError:
                        pass
                return {
                    "__runtime_type__": "string",
                    "__value__": result,
                    "result": result,
                    "success": result is not None,
                }

            elif command == "SET":
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                client.set(key, str(value))
                return {
                    "__runtime_type__": "string",
                    "__value__": "OK",
                    "result": "OK",
                    "success": True,
                }

            elif command == "HGET":
                result = client.hget(key, field)
                return {
                    "__runtime_type__": "string",
                    "__value__": result,
                    "result": result,
                    "success": result is not None,
                }

            elif command == "HSET":
                client.hset(key, field, str(value))
                return {
                    "__runtime_type__": "string",
                    "__value__": "OK",
                    "result": "OK",
                    "success": True,
                }

            elif command == "DEL":
                deleted = client.delete(key)
                return {
                    "__runtime_type__": "number",
                    "__value__": deleted,
                    "result": deleted,
                    "success": deleted > 0,
                }

            elif command == "KEYS":
                pattern = key if key else "*"
                keys = client.keys(pattern)
                return {
                    "__runtime_type__": "list",
                    "__value__": keys,
                    "result": keys,
                    "success": True,
                }

            else:
                return {"error": f"Unsupported Redis command: {command}"}

        except Exception as e:
            logger.exception("[Redis] Command '%s' failed: %s", command, e)
            return {"error": f"Redis {command} failed: {e}", "success": False}
