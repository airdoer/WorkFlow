import logging
import json
import urllib.request
import urllib.error
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class HTTPExecutor(BaseNodeExecutor):
    """HTTP Request node: perform HTTP GET/POST requests."""

    type = "http"

    def execute(self, config: dict, input_data: dict) -> dict:
        url = input_data.get("url", config.get("url", ""))
        method = config.get("method", "GET").upper()
        headers_str = config.get("headers", "{}")
        body = input_data.get("body", config.get("body", ""))
        timeout = int(config.get("timeout", 30))

        if not url:
            return {"error": "URL is required for HTTP node"}

        # Parse headers
        headers = {}
        try:
            if isinstance(headers_str, str) and headers_str.strip():
                headers = json.loads(headers_str)
            elif isinstance(headers_str, dict):
                headers = headers_str
        except json.JSONDecodeError:
            logger.warning("[HTTP] Invalid headers JSON: %s", headers_str)

        # Set default Content-Type for POST
        if method == "POST" and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        # Build request
        try:
            if isinstance(body, dict) or isinstance(body, list):
                body_data = json.dumps(body).encode("utf-8")
            elif isinstance(body, str):
                body_data = body.encode("utf-8")
            else:
                body_data = None

            req = urllib.request.Request(url, data=body_data, headers=headers, method=method)

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status_code = resp.status
                resp_body = resp.read().decode("utf-8", errors="replace")

                # Try to parse as JSON
                try:
                    response_data = json.loads(resp_body)
                except json.JSONDecodeError:
                    response_data = resp_body

                return {
                    "__runtime_type__": "object" if isinstance(response_data, dict) else "list" if isinstance(response_data, list) else "string",
                    "__value__": response_data,
                    "response": response_data,
                    "statusCode": status_code,
                    "success": 200 <= status_code < 300,
                }

        except urllib.error.HTTPError as e:
            return {
                "__runtime_type__": "string",
                "__value__": str(e),
                "response": str(e),
                "statusCode": e.code,
                "success": False,
                "error": f"HTTP {e.code}: {e.reason}",
            }
        except urllib.error.URLError as e:
            return {
                "__runtime_type__": "string",
                "__value__": str(e),
                "response": str(e),
                "statusCode": 0,
                "success": False,
                "error": f"URL Error: {e.reason}",
            }
        except Exception as e:
            logger.exception("[HTTP] Request failed: %s", e)
            return {"error": f"HTTP request failed: {e}"}
