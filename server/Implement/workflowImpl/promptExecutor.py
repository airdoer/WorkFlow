"""
Prompt Node Executor - Process prompts with LLM (DashScope)
"""
import os
import re
from typing import Dict, Any
from .nodeExecutor import BaseNodeExecutor


class PromptExecutor(BaseNodeExecutor):
    """Executor for Prompt nodes with LLM integration"""
    
    @property
    def type(self) -> str:
        return "prompt"
    
    async def execute(self, config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Prompt node
        
        Args:
            config: { 
                prompt: str, 
                temperature?: float, 
                model?: str, 
                maxTokens?: int 
            }
            input_data: Input from upstream nodes
            
        Returns:
            { 
                content: str, 
                model: str, 
                usage: { promptTokens: int, completionTokens: int } 
            }
        """
        prompt_template = config.get("prompt", "")
        temperature = config.get("temperature", 0.7)
        model = config.get("model", "qwen-plus")
        max_tokens = config.get("maxTokens", 4096)
        
        if not prompt_template:
            raise ValueError("prompt is required for Prompt node")
        
        # Perform variable interpolation
        prompt = self._interpolate_variables(prompt_template, input_data)
        
        # Call LLM API
        try:
            import openai
            
            # Get API key from environment
            api_key = os.getenv("DASHSCOPE_API_KEY")
            if not api_key:
                raise RuntimeError("DASHSCOPE_API_KEY environment variable is not set")
            
            # Initialize OpenAI-compatible client for DashScope
            client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            
            # Call chat completion API
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return {
                "content": response.choices[0].message.content,
                "model": model,
                "usage": {
                    "promptTokens": response.usage.prompt_tokens,
                    "completionTokens": response.usage.completion_tokens
                }
            }
            
        except ImportError:
            raise RuntimeError("openai package is not installed. Please install it with: pip install openai")
        except Exception as e:
            raise RuntimeError(f"LLM API call failed: {str(e)}")
    
    def _interpolate_variables(self, template: str, input_data: Dict[str, Any]) -> str:
        """
        Replace {{variable}} placeholders in template with actual values
        
        Args:
            template: Prompt template with {{nodeId.outputKey}} placeholders
            input_data: Input data from upstream nodes
            
        Returns:
            Interpolated prompt string
        """
        # Flatten nested input data
        flattened = self._flatten(input_data)
        
        # Replace all {{variable}} patterns
        def replace_var(match):
            var_name = match.group(1)
            value = flattened.get(var_name)
            return str(value) if value is not None else match.group(0)
        
        return re.sub(r'\{\{([^}]+)\}\}', replace_var, template)
    
    def _flatten(self, data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """
        Flatten nested dictionary with dot notation keys
        
        Args:
            data: Nested dictionary
            prefix: Key prefix for recursion
            
        Returns:
            Flattened dictionary with dot-notation keys
        """
        result = {}
        
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                result.update(self._flatten(value, full_key))
            else:
                result[full_key] = value
        
        return result
