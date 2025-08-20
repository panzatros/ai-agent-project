import json
from datetime import datetime
from typing import Dict, Callable, List
import requests
import logging
from couchbase.cluster import Cluster
from couchbase.auth import PasswordAuthenticator
from couchbase.options import ClusterOptions, QueryOptions
from couchbase.exceptions import DocumentNotFoundException

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

COUCHBASE_URL = "couchbase://localhost"
USERNAME = "Administrator"
PASSWORD = "Administrator"
CUSTOMERS_BUCKET_NAME = "customer_data"


class SimpleAgent:
    def __init__(self, model_name: str = "grok-3-mini", api_key: str = "xai-key"):
        self.model_name = model_name
        self.api_key = api_key
        self.tools = {}
        self.tool_schemas = []
        self.base_url = "https://api.x.ai/v1"
        self.system_prompt = (
            "You are a friendly, persuasive Sales AI chatbot. Your goal is to convince customers to keep their orders and explore more products. "
            "Use 'handle_complaint' tool for cancellation or complaint requests with customer_id and style in JSON format, e.g., Tool Call: handle_complaint(customer_id=\"CUST005\", style=\"AN209\", complaint=\"any\"). "
            "Use 'handle_general_question' tool for general questions with customer_id, style (optional), and question (passed as complaint when style is absent or extracted from complaint) in JSON format, e.g., Tool Call: handle_general_question(customer_id=\"CUST005\", style=\"AN209\", question=\"What are your latest products?\"). "
            "If no complaint or style is provided, assume it's the start of the chat and use a default like 'initial chat, ask what the customer needs help with'. "
            "For questions about specific products, extract the style code from the complaint if not provided in style field and include product details. "
            "Keep responses short, engaging, and professional. Always recommend alternative products. "
            "Check previous messages to avoid repetition and maintain coherent conversation using customer_id as reference."
        )
        self.cluster = Cluster(COUCHBASE_URL, ClusterOptions(PasswordAuthenticator(USERNAME, PASSWORD)))
        self.customers_bucket = self.cluster.bucket(CUSTOMERS_BUCKET_NAME)
        self.customers_collection = self.customers_bucket.default_collection()

    def register_tool(self, schema: Dict, function: Callable):
        tool_name = schema["function"]["name"]
        self.tools[tool_name] = function
        self.tool_schemas.append({"type": "function", "function": schema["function"]})
        logger.debug(f"Registered tool: {tool_name}")

    def get_conversation_history(self, customer_id: str, limit: int = 10) -> list:
        """Retrieve the last 'limit' messages for a customer."""
        try:
            result = self.customers_collection.get(customer_id)
            customer = result.content_as[dict]
            history = customer.get("conversation_history", [])
            logger.debug(f"Retrieved {len(history)} messages for customer {customer_id}")
            return history[-limit:]  # Return the last 'limit' messages
        except DocumentNotFoundException:
            logger.warning(f"No conversation history found for customer {customer_id}")
            return []
        except Exception as e:
            logger.error(f"Error retrieving conversation history for {customer_id}: {str(e)}")
            return []

    def save_conversation_turn(self, customer_id: str, role: str, content: str):
        """Save a conversation turn to Couchbase."""
        try:
            timestamp = datetime.now().isoformat()
            message = {"role": role, "content": content, "timestamp": timestamp}
            result = self.customers_collection.get(customer_id)
            customer = result.content_as[dict]
            customer.setdefault("conversation_history", []).append(message)
            self.customers_collection.upsert(customer_id, customer)
            logger.debug(f"Saved conversation turn for {customer_id}: {message}")
        except DocumentNotFoundException:
            # Create new customer document if it doesn't exist
            customer = {"conversation_history": [message], "customer_id": customer_id}
            self.customers_collection.upsert(customer_id, customer)
            logger.debug(f"Created new customer document with conversation for {customer_id}")
        except Exception as e:
            logger.error(f"Error saving conversation turn for {customer_id}: {str(e)}")

    def chat(self, message: str, customer_id: str, use_tools: bool = False) -> str:
        logger.debug(f"Calling chat with message: {message}, customer_id: {customer_id}, use_tools: {use_tools}")
        try:
            # Save user message
            self.save_conversation_turn(customer_id, "user", message)
            # Get conversation history
            history = self.get_conversation_history(customer_id)
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            # Build messages with history
            messages = [{"role": "system", "content": self.system_prompt}] + history + [{"role": "user", "content": message}]
            payload = {
                "model": self.model_name,
                "messages": messages
            }
            if use_tools and self.tools:
                payload["tools"] = self.tool_schemas
            logger.debug(f"Sending Grok API request in chat: {json.dumps(payload, indent=2)}")
            logger.debug(f"Headers: {headers}")
            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            response_data = response.json()
            logger.debug(f"Grok API response in chat: {json.dumps(response_data, indent=2)}")
            tool_calls = response_data.get("choices", [{}])[0].get("message", {}).get("tool_calls")
            if isinstance(tool_calls, str):
                try:
                    tool_calls = json.loads(tool_calls).get("tool_calls", [])
                except json.JSONDecodeError:
                    logger.error("Failed to parse tool_calls string")
                    tool_calls = []
            logger.debug(f"Parsed tool_calls: {tool_calls}")
            if use_tools and tool_calls:
                logger.debug("Entering tool_calls block")
                response_content = self._handle_tool_calls(message, response_data)
                # Save assistant response
                self.save_conversation_turn(customer_id, "assistant", response_content)
                return response_content
            content = response_data["choices"][0]["message"]["content"]
            # Save assistant response
            self.save_conversation_turn(customer_id, "assistant", content)
            return content
        except requests.exceptions.HTTPError as e:
            error_response = e.response.json() if e.response else {}
            logger.error(f"HTTP error in chat: {e.response.status_code} - {json.dumps(error_response, indent=2)}")
            self.save_conversation_turn(customer_id, "assistant", f"Error: HTTP {e.response.status_code}")
            return f"Error: HTTP {e.response.status_code} - {json.dumps(error_response, indent=2)}"
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            self.save_conversation_turn(customer_id, "assistant", f"Error: {str(e)}")
            return f"Error: {str(e)}"

    def _handle_tool_calls(self, original_message: str, response_data: Dict) -> str:
        logger.debug(f"Handling tool calls for message: {original_message}")
        tool_calls = response_data.get("choices", [{}])[0].get("message", {}).get("tool_calls")
        if isinstance(tool_calls, str):
            try:
                tool_calls = json.loads(tool_calls).get("tool_calls", [])
            except json.JSONDecodeError:
                logger.error("Failed to parse tool_calls string")
                return "Error: Invalid tool call format"
        for tool_call in tool_calls:
            function_name = tool_call.get("function", {}).get("name")
            arguments = tool_call.get("function", {}).get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if function_name in self.tools:
                logger.debug(f"Calling tool {function_name} with arguments: {arguments}")
                try:
                    result = self.tools[function_name](**arguments, api_key=self.api_key)
                    return result
                except Exception as e:
                    logger.error(f"Error executing tool {function_name}: {str(e)}")
                    return f"Error executing tool {function_name}: {str(e)}"
        return "No valid tool calls found"