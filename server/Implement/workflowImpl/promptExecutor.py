import os
import re
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class PromptExecutor(BaseNodeExecutor):
    type = "prompt"

    async def execute(self, config: dict, input_data: dict) -> dict:
        prompt = config.get("prompt", "")
        temperature = config.get("temperature", 0.7)
        model = config.get("model", "qwen-plus")
        max_tokens = config.get("maxTokens", 4096)

        if not prompt:
            return {"error": "prompt is required"}

        for key, value in self._flatten(input_data).items():
            prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

        try:
            import openai
            client = openai.AsyncOpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY", ""),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )

            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return {
                "content": response.choices[0].message.content,
                "model": model,
                "usage": {
                    "promptTokens": response.usage.prompt_tokens if response.usage else 0,
                    "completionTokens": response.usage.completion_tokens if response.usage else 0,
                }
            }
        except Exception as e:
            return {"error": str(e)}

    def _flatten(self, data: dict, prefix: str = "") -> dict:
        result = {}
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                result.update(self._flatten(v, key))
            else:
                result[key] = v
        return result
