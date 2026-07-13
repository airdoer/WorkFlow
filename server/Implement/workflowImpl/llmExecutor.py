import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
from Implement.workflowImpl.expressionEngine import get_expression_engine

logger = logging.getLogger(__name__)


class LLMExecutor(BaseNodeExecutor):
    """
    LLM node: raw LLM call (no prompt template).
    
    Unlike PromptExecutor, this node sends the input message directly to the LLM.
    """

    type = "llm"

    def execute(self, config: dict, input_data: dict) -> dict:
        message = input_data.get("message", input_data.get("value", ""))
        system_prompt = input_data.get("systemPrompt", config.get("systemPrompt", ""))
        model = config.get("model", "")
        temperature = float(config.get("temperature", 0.7))
        max_tokens = int(config.get("maxTokens", 2048))

        if not message:
            return {"error": "Message is required for LLM node"}

        # Use the same LLM API as PromptExecutor
        try:
            from Implement.workflowImpl.promptExecutor import PromptExecutor
            prompt_exec = PromptExecutor()

            # Build a prompt config from the LLM config
            prompt_config = {
                "prompt": message,
                "model": model,
                "temperature": temperature,
            }
            if system_prompt:
                # Prepend system prompt
                prompt_config["prompt"] = f"[System]: {system_prompt}\n\n[User]: {message}"

            prompt_input = {"context": input_data.get("context", {})}
            result = prompt_exec.execute(prompt_config, prompt_input)

            return {
                "__runtime_type__": "string",
                "__value__": result.get("content", ""),
                "response": result.get("content", ""),
                "model": result.get("model", model),
                "usage": result.get("usage", {}),
                "success": "error" not in result,
            }

        except Exception as e:
            logger.exception("[LLM] Error: %s", e)
            return {"error": f"LLM call failed: {e}"}
