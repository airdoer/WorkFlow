import time
import logging
from utility import aiUtils
import openai
import os

# 添加代理
# 国内：
# http_proxy=10.164.57.167:11080
# https_proxy=http://10.164.57.167:11080
# 国外：
# http_proxy=http://10.156.73.36:11080 \
# https_proxy=http://10.156.73.36:11080 \


inner_proxy = {
    "http": "http://10.52.57.90:11080",
    "https": "http://10.52.57.90:11080",
}

internal_proxy = {
    "http": "http://10.74.176.8:11080",
    "https": "http://10.74.176.8:11080",
}

os.environ.setdefault("HTTP_PROXY", inner_proxy["http"])
os.environ.setdefault("HTTPS_PROXY", inner_proxy["https"])

# 配置 key 和 base_url
openai.api_key = aiUtils.DASHSCOPE_API_KEY or os.getenv("DASHSCOPE_API_KEY")
openai.api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def aiRequest(prompt: str) -> str:
    """
    向 ChatGPT 请求回答
    """
    start_time = time.time()

    completion = openai.ChatCompletion.create(
        model=aiUtils.MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        request_timeout=20,
    )

    end_time = time.time()
    logging.info(f"AIRequest {prompt} 请求耗时: {end_time - start_time} 秒")
    logging.info(f"aiRequest Result: {completion}")

# Result: {
#   "choices": [
#     {
#       "message": {
#         "content": "Hello! I am Qwen, a large-scale language model independently developed by the Tongyi Lab under Alibaba Group. I can assist you with answering questions, writing, logical reasoning, programming, and more. I support multiple languages, including Chinese, English, German, French, Spanish, Portuguese, Italian, Dutch, Russian, Czech, Polish, Arabic, Persian, Hebrew, Turkish, Japanese, Korean, and many others.\n\nFeel free to ask me anything or let me know if you need help with a specific task! \ud83d\ude0a",
#         "role": "assistant"
#       },
#       "finish_reason": "stop",
#       "index": 0,
#       "logprobs": null
#     }
#   ],
#   "object": "chat.completion",
#   "usage": {
#     "prompt_tokens": 23,
#     "completion_tokens": 106,
#     "total_tokens": 129,
#     "prompt_tokens_details": {
#       "cached_tokens": 0
#     }
#   },
#   "created": 1763044950,
#   "system_fingerprint": null,
#   "model": "qwen3-max",
#   "id": "chatcmpl-f3b1e9b4-cd67-44d7-9582-1f2b7aa61cc0"
# }


    # 返回回答文本
    return completion["choices"][0]["message"]["content"]

# from Implement.aiImpl import aiImp
# aiImp.aiRequest("Who are you ")
