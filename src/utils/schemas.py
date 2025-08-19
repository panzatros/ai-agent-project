time_tool_schema = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Returns the current date and time in a specified timezone (default: US/Central).",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Timezone name (e.g., 'US/Central', 'UTC')."
                }
            },
            "required": []
        }
    }
}


handle_cancellation_schema = {
    "function": {
        "name": "handle_cancellation",
        "description": "Processes a cancellation request by generating and (simulating) sending a persuasive message to retain the order, using data from Couchbase.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "The unique ID of the customer requesting cancellation."
                },
                "style": {
                    "type": "string",
                    "description": "The style code of the product they wish to cancel."
                }
            },
            "required": ["customer_id", "style"]
        }
    }
}

handle_complaint_schema = {
    "type": "function",
    "function": {
        "name": "handle_complaint",
        "description": "Handles a customer complaint or cancellation request by generating a persuasive response with product suggestions and incentives, using data from Couchbase.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "The unique ID of the customer with the complaint or cancellation request."
                },
                "style": {
                    "type": "string",
                    "description": "The style code of the product related to the complaint or cancellation."
                },
                "complaint": {
                    "type": "string",
                    "description": "The customer's specific complaint or reason for cancellation (optional, null for first-time cancellation)."
                }
            },
            "required": ["customer_id", "style"]
        }
    }
}