from flask import Flask, request, jsonify, Blueprint
#from agents.simple_agent import SimpleAgent
from agents.grok_agent import SimpleAgent
import json
from utils.tool_utils import get_current_time, handle_complaint
from utils.schemas import time_tool_schema, handle_complaint_schema
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize the agent globally
agent = SimpleAgent()
agent.register_tool(time_tool_schema, get_current_time)
agent.register_tool(handle_complaint_schema, handle_complaint)
# Create a Flask Blueprint for routes

routes = Blueprint("routes", __name__)

@routes.route('/ask', methods=['POST'])
def ask():
    """Endpoint to handle user queries and return agent responses."""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({"error": "Missing 'query' in JSON payload"}), 400
        
        query = data['query']
        response = agent.chat(query)
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@routes.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({"status": "ok"}), 200


@routes.route('/tools', methods=['GET'])
def list_tools():
    """Endpoint to list available tools and their schemas."""
    return jsonify({"tools": agent.tool_schemas}), 200


@routes.route('/cancel', methods=['POST'])
def cancel_order():
    try:
        data = request.get_json()
        logger.debug(f"Received request: {json.dumps(data, indent=2)}")
        customer_id = data.get('customer_id')
        style = data.get('style')
        if not customer_id or not style:
            return jsonify({"error": "Missing customer_id or style"}), 400

        # Use the agent to handle the cancellation
        # Test without tools to isolate issue
        response = agent.chat(f"Handle cancellation for customer {customer_id} and style {style}", use_tools=False)
        logger.debug(f"Agent response: {response}")
        return jsonify({"message": response}), 200
    except Exception as e:
        logger.error(f"Error in cancel_order: {str(e)}")
        return jsonify({"error": str(e)}), 500
"""
@routes.route('/retain', methods=['POST'])
def handle_complain():
    try:
        data = request.get_json()
        customer_id = data.get('customer_id')
        style = data.get('style')
        complain = data.get('complain')
        if not customer_id or not style:
            return jsonify({"error": "Missing customer_id or product ID"}), 400

        # Use the agent to handle the complaint
        if complain is None:
            response = agent.chat(f"Handle cancellation for customer {customer_id} and style {style}", use_tools=True)
        else:
            response = agent.chat(f"Handle complaint for customer {customer_id} and style {style} with complain: {complain}")
        return jsonify({"message": response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
"""

    
@routes.route('/retain', methods=['POST'])
def handle_complain():
    try:
        data = request.get_json()
        customer_id = data.get('customer_id')
        style = data.get('style')
        complaint = data.get('complaint')  # Can be None for first-time cancellation
        if not customer_id or not style:
            return jsonify({"error": "Missing customer_id or style"}), 400

        # Use the agent to call the handle_complaint tool
        response = agent.chat(
            f"Handle complaint or cancellation for customer {customer_id} and style {style} with complaint: {complaint or 'None'}",
            customer_id=customer_id,
            use_tools=True
        )
        return jsonify({"message": response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500