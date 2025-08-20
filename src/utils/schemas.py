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

handle_general_question_schema = {
    "type": "function",
    "function": {
        "name": "handle_general_question",
        "description": "Handles a general customer question by generating a concise response with product recommendations and incentives, using data from Couchbase.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "The unique ID of the customer asking the question."
                },
                "style": {
                    "type": "string",
                    "description": "The style which represent a product, may or may not be on the request."
                },
                "question": {
                    "type": "string",
                    "description": "The customer's general question."
                }
            },
            "required": ["customer_id", "question"]
        }
    }
}

mock_purchase_schema = {
    "type": "function",
    "function": {
        "name": "mock_purchase",
        "description": "Simulates a purchase by adding it to the customer's purchase history in Couchbase and generates a confirmation response with product recommendations.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "The unique ID of the customer making the purchase."
                },
                "style": {
                    "type": "string",
                    "description": "The style code of the product being purchased."
                }
            },
            "required": ["customer_id", "style"]
        }
    }
}