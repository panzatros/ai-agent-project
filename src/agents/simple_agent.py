import ollama
import json
from datetime import datetime
from typing import Dict, Callable, List

class SimpleAgent:
    def __init__(self, model_name: str = "llama3.1"):
        self.model_name = model_name
        self.tools = {}
        self.tool_schemas = []
        # System prompt to encourage tool usage
        self.system_prompt = (
            "you are the best Sales Ai this side of the mississippi. "
            "you task are try and convince people to not cancel, and buy at most as posible. "
            "you have access to tools that can help you with this task. "
            "use them when you think they will help. "
            "if you need to use a tool, you will call it by name and provide the necessary arguments. "
            "if you don't know the answer, you will use the tools to find it. "
            "if you don't know how to use a tool, you will ask the user for help. "
        )

    def register_tool(self, schema: Dict, function: Callable):
        """Register a tool for the agent to use."""
        tool_name = schema["function"]["name"]
        self.tools[tool_name] = function
        self.tool_schemas.append(schema)

    def chat(self, message: str) -> str:
        """Process a user message and return a response."""
        try:
            # Include system prompt and user message
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": message}
            ]
            response = ollama.chat(
                model=self.model_name,
                messages=messages,
                tools=self.tool_schemas
            )
            if response.get("message", {}).get("tool_calls"):
                return self._handle_tool_calls(message, response)
            return response["message"]["content"]
        except Exception as e:
            return f"Error: {str(e)}"

    def _handle_tool_calls(self, original_message: str, response: Dict) -> str:
        """Handle tool calls and return the final response."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": original_message},
            response["message"]
        ]
        for tool_call in response["message"]["tool_calls"]:
            function_name = tool_call["function"]["name"]
            function_args = tool_call["function"]["arguments"]
            if isinstance(function_args, str):
                function_args = json.loads(function_args)
            if function_name in self.tools:
                result = self.tools[function_name](**function_args)
                messages.append({
                    "role": "tool",
                    "content": str(result),
                    "tool_call_id": tool_call.get("id", "")
                })
        final_response = ollama.chat(model=self.model_name, messages=messages)
        return final_response["message"]["content"]