import json
from datetime import datetime
from typing import Dict, Callable, List
import requests
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleAgent:
    def __init__(self, model_name: str = "grok-4", api_key: str = "key"):
        self.model_name = model_name
        self.api_key = api_key
        self.tools = {}
        self.tool_schemas = []
        self.base_url = "https://api.x.ai/v1"
        self.system_prompt = (
            "You are the best Sales AI this side of the Mississippi. "
            "Your task is to convince people not to cancel and to buy as much as possible. "
            "You have access to the 'handle_complaint' tool, which processes cancellation requests and generates persuasive messages. "
            "When a user requests to cancel an order, use the 'handle_complaint' tool with the provided customer_id and style. "
            "Provide the tool's arguments in JSON format, e.g., Tool Call: get_order_details(customer_id=\"CUST005\", style=\"AN209\", complaint=\"any\")"
            "if complain is not present on the request, it means that is the beggining of the chat, so you can fill it with something like \"this is the beggining on the chat no complain yet, we muct ask why the user is disgruntle with product \""
            "Do not generate a text description of the tool call; invoke the tool directly."
            "this is like a chatbot directly talking to the  customer, with that im mind try to keep it clean and short without unnecesary details"
            "please check previous messages and assure that you are not repeating yourself, and that you are not asking the same question twice. "
            "also use them as reference to keep a coherent conversation with the user. "
            "use the customer_id as reference to know if the customer is having a conversation or not "
        )

    def register_tool(self, schema: Dict, function: Callable):
        tool_name = schema["function"]["name"]
        self.tools[tool_name] = function
        self.tool_schemas.append({"type": "function", "function": schema["function"]})
        logger.debug(f"Registered tool: {tool_name}")

    def chat(self, message: str, use_tools: bool = True) -> str:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": message}
            ]
            payload = {
                "model": self.model_name,
                "messages": messages
            }
            if use_tools and self.tool_schemas:
                logger.debug("Using tools in Grok API request in chat")
                payload["tools"] = self.tool_schemas
            logger.debug(f"Sending Grok API request in chat: {json.dumps(payload, indent=2)}")
            # Log the full request details
            logger.debug(f"Preparing Grok API request in chat with model {self.model_name}:")
            logger.debug(f"URL: {self.base_url}/chat/completions")
            logger.debug(f"Headers: {json.dumps(headers, indent=2)}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            response_data = response.json()
            logger.debug(f"Grok API response in chat: {json.dumps(response_data, indent=2)}")
            if use_tools and response_data.get("choices", [{}])[0].get("message", {}).get("tool_calls"):
                logger.debug("Handling tool calls in response")
                return self._handle_tool_calls(message, response_data)
            return response_data["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as e:
            error_response = e.response.json() if e.response else {}
            logger.error(f"HTTP error in chat: {e.response.status_code} - {json.dumps(error_response, indent=2)}")
            return f"Error: HTTP {e.response.status_code} - {json.dumps(error_response, indent=2)}"
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            return f"Error: {str(e)}"

    def _handle_tool_calls(self, original_message: str, response: Dict) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": original_message},
            response["choices"][0]["message"]
        ]
        for tool_call in response["choices"][0]["message"].get("tool_calls", []):
            function_name = tool_call["function"]["name"]
            function_args = tool_call["function"]["arguments"]
            if isinstance(function_args, str):
                try:
                    function_args = json.loads(function_args)
                except json.JSONDecodeError:
                    logger.error(f"Invalid function arguments for {function_name}: {function_args}")
                    return f"Error: Invalid function arguments for {function_name}"
            if function_name in self.tools:
                try:
                    result = self.tools[function_name](**function_args, api_key=self.api_key)
                    messages.append({
                        "role": "tool",
                        "content": str(result),
                        "tool_call_id": tool_call.get("id", "")
                    })
                except Exception as e:
                    logger.error(f"Error executing tool {function_name}: {str(e)}")
                    return f"Error executing tool {function_name}: {str(e)}"
            else:
                logger.error(f"Tool {function_name} not found")
                return f"Error: Tool {function_name} not found"
        logger.debug(f"Sending tool response to Grok API: {json.dumps(messages, indent=2)}")
        final_response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json={
                "model": self.model_name,
                "messages": messages
            }
        )
        final_response.raise_for_status()
        response_data = final_response.json()
        logger.debug(f"Final Grok API response: {json.dumps(response_data, indent=2)}")
        return response_data["choices"][0]["message"]["content"]