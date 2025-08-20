import ollama
import json
import pytz
import requests
import re  # Added for style extraction in handle_general_question
from datetime import datetime
from typing import Dict, Callable, List
from flask import Flask, request, jsonify
from couchbase.cluster import Cluster
from couchbase.auth import PasswordAuthenticator
from couchbase.options import ClusterOptions, QueryOptions
import os
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_current_time(timezone: str = "US/Central") -> str:
    try:
        tz = pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.timezone("US/Central")
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

COUCHBASE_URL = "couchbase://localhost"
USERNAME = "Administrator"
PASSWORD = "Administrator"
CUSTOMERS_BUCKET_NAME = "customer_data"
PRODUCTS_BUCKET_NAME = "products"
SALES_STATS_BUCKET_NAME = "sales_cache"
SALES_STATS_DOCUMENT_KEY = "total_sales_stats"

# Initialize Couchbase cluster
cluster = Cluster(COUCHBASE_URL, ClusterOptions(PasswordAuthenticator(USERNAME, PASSWORD)))
customers_bucket = cluster.bucket(CUSTOMERS_BUCKET_NAME)
products_bucket = cluster.bucket(PRODUCTS_BUCKET_NAME)
sales_stats_bucket = cluster.bucket(SALES_STATS_BUCKET_NAME)
customers_collection = customers_bucket.default_collection()
products_collection = products_bucket.default_collection()
sales_stats_collection = sales_stats_bucket.default_collection()

# Cache for sales stats
_sales_stats_cache = None

def get_customer(customer_id: str) -> Dict:
    try:
        result = customers_collection.get(customer_id)
        logger.debug(f"Fetched customer {customer_id}: {result.content_as[dict]}")
        return result.content_as[dict]
    except Exception as e:
        logger.error(f"Error fetching customer {customer_id}: {str(e)}")
        return None

def get_product(style: str) -> Dict:
    try:
        result = products_collection.get(style)
        logger.debug(f"Fetched product {style}: {result.content_as[dict]}")
        return result.content_as[dict]
    except Exception as e:
        logger.error(f"Error fetching product {style}: {str(e)}")
        return None

def get_sales_stats(style: str) -> Dict:
    global _sales_stats_cache
    try:
        if _sales_stats_cache is None:
            result = sales_stats_collection.get(SALES_STATS_DOCUMENT_KEY)
            _sales_stats_cache = result.content_as[dict]
        stats = _sales_stats_cache.get("style_status_counts", {}).get(style, {"total_count": 0, "status_counts": {}})
        logger.debug(f"Sales stats for {style}: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Error fetching sales stats for {style}: {str(e)}")
        return {"total_count": 0, "status_counts": {}}

def get_similar_products(category: str, exclude_style: str = None, limit: int = 3) -> list:
    try:
        # Updated query to select fields from the new product structure
        query = f"SELECT style, description, price, color, accessory_type, features, usage_type FROM {PRODUCTS_BUCKET_NAME} WHERE category = $1"
        params = [category]
        if exclude_style:
            query += " AND style != $2 LIMIT $3"
            params.extend([exclude_style, limit])
        else:
            query += " LIMIT $2"
            params.append(limit)
        result = cluster.query(query, QueryOptions(positional_parameters=params))
        products = [row for row in result]
        logger.debug(f"Fetched {len(products)} similar products for category {category}")
        return products
    except Exception as e:
        logger.error(f"Error fetching similar products for category {category}: {str(e)}")
        return []

def handle_complaint(customer_id: str, style: str, complaint: str, api_key: str, agent: 'SimpleAgent' = None) -> str:
    logger.debug(f"Handling complaint for customer_id: {customer_id}, style: {style}, complaint: {complaint}")
    
    customer = get_customer(customer_id)
    if not customer:
        return f"Customer {customer_id} not found in Couchbase bucket '{CUSTOMERS_BUCKET_NAME}'."

    product = get_product(style)
    if not product:
        return f"Product style {style} not found in Couchbase bucket '{PRODUCTS_BUCKET_NAME}'."

    sales_stats = get_sales_stats(style)
    purchase = next((p for p in customer.get("purchase_history", []) if p["style"] == style), None)
    if not purchase:
        return f"No purchase of {style} found for customer {customer_id}."

    similar_products = get_similar_products(customer.get("preferred_category", product["category"]), style)
    # Updated similar products text to use new fields
    similar_products_text = "\n".join([
        f"- {p['description']} (Style: {p['style']}, Price: ${p['price']}, Color: {p['color']}, "
        f"Type: {p.get('accessory_type', 'N/A')}, Features: {', '.join(p.get('features', [])) or 'None'}, "
        f"Usage: {p.get('usage_type', 'N/A')})"
        for p in similar_products
    ]) if similar_products else "No similar products found."

    discount_offer = ""
    if customer.get("loyalty_level") in ["Gold", "Platinum"]:
        discount_offer = "15% off your next purchase or free shipping."
    elif customer.get("loyalty_level") == "Silver":
        discount_offer = "10% off a replacement or next purchase."
    else:
        discount_offer = "5% off your next purchase."

    # Updated prompt to use new product fields
    if complaint:
        prompt = (
            f"Customer {customer['name']} ({customer['loyalty_level']}) complained about {style}: {product['description']} "
            f"(${product['price']}, {product['color']}, Type: {product.get('accessory_type', 'N/A')}, "
            f"Features: {', '.join(product.get('features', [])) or 'None'}, Usage: {product.get('usage_type', 'N/A')}). "
            f"Complaint: {complaint}. Preferred category: {customer['preferred_category']}. "
            f"Alternatives: {similar_products_text}. "
            f"Respond briefly: empathize, apologize, offer {discount_offer} or replacement, suggest alternatives, and encourage further dialogue."
        )
    else:
        prompt = (
            f"Customer {customer['name']} ({customer['loyalty_level']}) wants to cancel {style}: {product['description']} "
            f"(${product['price']}, {product['color']}, Type: {product.get('accessory_type', 'N/A')}, "
            f"Features: {', '.join(product.get('features', [])) or 'None'}, Usage: {product.get('usage_type', 'N/A')}). "
            f"Preferred category: {customer['preferred_category']}. Alternatives: {similar_products_text}. "
            f"Respond briefly: highlight product benefits, offer {discount_offer}, suggest alternatives, and note return option."
        )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "grok-3-mini",
            "messages": [{"role": "user", "content": prompt}]
        }
        logger.debug(f"Sending Grok API request in handle_complaint: {json.dumps(payload, indent=2)}")
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        response_data = response.json()
        logger.debug(f"Grok API response in handle_complaint: {json.dumps(response_data, indent=2)}")
        message = response_data["choices"][0]["message"]["content"]
        if agent:
            agent.save_conversation_turn(customer_id, "assistant", message)
        return f"{message}"
    except requests.exceptions.HTTPError as e:
        error_response = e.response.json() if e.response else {}
        logger.error(f"HTTP error in handle_complaint: {e.response.status_code} - {json.dumps(error_response, indent=2)}")
        if agent:
            agent.save_conversation_turn(customer_id, "assistant", f"Error: HTTP {e.response.status_code}")
        return f"Error generating message: HTTP {e.response.status_code} - {json.dumps(error_response, indent=2)}"
    except Exception as e:
        logger.error(f"Error in handle_complaint: {str(e)}")
        if agent:
            agent.save_conversation_turn(customer_id, "assistant", f"Error: {str(e)}")
        return f"Error generating message: {str(e)}"

def handle_general_question(customer_id: str, style: str, question: str, api_key: str, agent: 'SimpleAgent' = None) -> str:
    logger.debug(f"Handling general question for customer_id: {customer_id}, style: {style}, question: {question}")
    
    customer = get_customer(customer_id)
    if not customer:
        return f"Customer {customer_id} not found in Couchbase bucket '{CUSTOMERS_BUCKET_NAME}'."

    # Check if question references a specific product style
    product_style = style
    if not product_style:
        # Try to extract style from question (e.g., "AN201" in "tell me about product AN201")
        style_match = re.search(r'\b[A-Z0-9]{4,5}\b', question)
        product_style = style_match.group(0) if style_match else None

    product_details = ""
    category = customer.get("preferred_category", "General")
    if product_style:
        product = get_product(product_style)
        if product:
            category = product.get("category", category)
            # Updated product details to use new fields
            product_details = (
                f"{product['description']} (Style: {product_style}, Price: ${product['price']}, "
                f"Color: {product['color']}, Type: {product.get('accessory_type', 'N/A')}, "
                f"Features: {', '.join(product.get('features', [])) or 'None'}, Usage: {product.get('usage_type', 'N/A')}). "
            )
        else:
            product_details = f"Product style {product_style} not found. "

    similar_products = get_similar_products(category, product_style)
    # Updated similar products text to use new fields
    similar_products_text = "\n".join([
        f"- {p['description']} (Style: {p['style']}, Price: ${p['price']}, Color: {p['color']}, "
        f"Type: {p.get('accessory_type', 'N/A')}, Features: {', '.join(p.get('features', [])) or 'None'}, "
        f"Usage: {p.get('usage_type', 'N/A')})"
        for p in similar_products
    ]) if similar_products else "No similar products found."

    discount_offer = ""
    if customer.get("loyalty_level") in ["Gold", "Platinum"]:
        discount_offer = "15% off your next purchase or free shipping."
    elif customer.get("loyalty_level") == "Silver":
        discount_offer = "10% off your next purchase."
    else:
        discount_offer = "5% off your next purchase."

    # Updated prompt to use new product fields
    prompt = (
        f"Customer {customer['name']} ({customer['loyalty_level']}) asked: {question}. "
        f"Preferred category: {category}. Purchase history: {json.dumps(customer['purchase_history'])}. "
        f"{product_details}Recommended products: {similar_products_text}. "
        f"Respond briefly: answer the question clearly (include product details if requested), offer {discount_offer}, suggest recommended products, and invite further questions."
    )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "grok-3-mini",
            "messages": [{"role": "user", "content": prompt}]
        }
        logger.debug(f"Sending Grok API request in handle_general_question: {json.dumps(payload, indent=2)}")
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        response_data = response.json()
        logger.debug(f"Grok API response in handle_general_question: {json.dumps(response_data, indent=2)}")
        message = response_data["choices"][0]["message"]["content"]
        if agent:
            agent.save_conversation_turn(customer_id, "assistant", message)
        return f"{message}"
    except requests.exceptions.HTTPError as e:
        error_response = e.response.json() if e.response else {}
        logger.error(f"HTTP error in handle_general_question: {e.response.status_code} - {json.dumps(error_response, indent=2)}")
        if agent:
            agent.save_conversation_turn(customer_id, "assistant", f"Error: HTTP {e.response.status_code}")
        return f"Error generating message: HTTP {e.response.status_code} - {json.dumps(error_response, indent=2)}"
    except Exception as e:
        logger.error(f"Error in handle_general_question: {str(e)}")
        if agent:
            agent.save_conversation_turn(customer_id, "assistant", f"Error: {str(e)}")
        return f"Error generating message: {str(e)}"

def mock_purchase(customer_id: str, style: str, api_key: str, agent: 'SimpleAgent' = None) -> str:
    logger.debug(f"Mocking purchase for customer_id: {customer_id}, style: {style}")
    
    customer = get_customer(customer_id)
    if not customer:
        return f"Customer {customer_id} not found in Couchbase bucket '{CUSTOMERS_BUCKET_NAME}'."

    product = get_product(style)
    if not product:
        return f"Product style {style} not found in Couchbase bucket '{PRODUCTS_BUCKET_NAME}'."

    # Create mock purchase details matching the customer purchase history structure
    purchase = {
        "style": style,
        "purchase_date": get_current_time(),
        "quantity": 1,
        "amount": round(product["price"], 2),
        "status": "Ordered"
    }

    # Update customer's purchase history and related fields
    try:
        customer["purchase_history"] = customer.get("purchase_history", []) + [purchase]
        customer["total_spent"] = round(customer.get("total_spent", 0) + purchase["amount"], 2)
        customer["num_purchases"] = customer.get("num_purchases", 0) + 1
        customer["last_purchase_date"] = purchase["purchase_date"]
        customers_collection.upsert(customer_id, customer)
        logger.debug(f"Updated purchase history for customer {customer_id}")
    except Exception as e:
        logger.error(f"Error updating purchase history for {customer_id}: {str(e)}")
        return f"Error updating purchase history: {str(e)}"

    similar_products = get_similar_products(product["category"], style)
    # Updated similar products text to use new fields
    similar_products_text = "\n".join([
        f"- {p['description']} (Style: {p['style']}, Price: ${p['price']}, Color: {p['color']}, "
        f"Type: {p.get('accessory_type', 'N/A')}, Features: {', '.join(p.get('features', [])) or 'None'}, "
        f"Usage: {p.get('usage_type', 'N/A')})"
        for p in similar_products
    ]) if similar_products else "No similar products found."

    discount_offer = ""
    if customer.get("loyalty_level") in ["Gold", "Platinum"]:
        discount_offer = "15% off your next purchase or free shipping."
    elif customer.get("loyalty_level") == "Silver":
        discount_offer = "10% off your next purchase."
    else:
        discount_offer = "5% off your next purchase."

    # Updated prompt to use new product fields
    prompt = (
        f"Customer {customer['name']} ({customer['loyalty_level']}) successfully purchased {style}: {product['description']} "
        f"(${product['price']}, {product['color']}, Type: {product.get('accessory_type', 'N/A')}, "
        f"Features: {', '.join(product.get('features', [])) or 'None'}, Usage: {product.get('usage_type', 'N/A')}). "
        f"Preferred category: {customer.get('preferred_category', product['category'])}. "
        f"Recommended products: {similar_products_text}. "
        f"Respond briefly: confirm the purchase, highlight product benefits, offer {discount_offer}, suggest recommended products, and invite further questions."
    )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "grok-3-mini",  # Changed to grok-3-mini to match other methods
            "messages": [{"role": "user", "content": prompt}]
        }
        logger.debug(f"Sending Grok API request in mock_purchase: {json.dumps(payload, indent=2)}")
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        response_data = response.json()
        logger.debug(f"Grok API response in mock_purchase: {json.dumps(response_data, indent=2)}")
        message = response_data["choices"][0]["message"]["content"]
        if agent:
            agent.save_conversation_turn(customer_id, "assistant", message)
        return f"{message}"
    except requests.exceptions.HTTPError as e:
        error_response = e.response.json() if e.response else {}
        logger.error(f"HTTP error in mock_purchase: {e.response.status_code} - {json.dumps(error_response, indent=2)}")
        if agent:
            agent.save_conversation_turn(customer_id, "assistant", f"Error: HTTP {e.response.status_code}")
        return f"Error generating message: HTTP {e.response.status_code} - {json.dumps(error_response, indent=2)}"
    except Exception as e:
        logger.error(f"Error in mock_purchase: {str(e)}")
        if agent:
            agent.save_conversation_turn(customer_id, "assistant", f"Error: {str(e)}")
        return f"Error generating message: {str(e)}"