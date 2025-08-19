import ollama
import json
import pytz
import requests
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

def get_similar_products(category: str, exclude_style: str, limit: int = 3) -> list:
    try:
        query = f"SELECT style, description, price, color, fit, occasion FROM {PRODUCTS_BUCKET_NAME} WHERE category = $1 AND style != $2 LIMIT $3"
        result = cluster.query(query, QueryOptions(positional_parameters=[category, exclude_style, limit]))
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
    similar_products_text = "\n".join([
        f"- {p['description']} (Style: {p['style']}, Price: ${p['price']}, Color: {p['color']}, Fit: {p['fit']}, Occasion: {p['occasion']})"
        for p in similar_products
    ]) if similar_products else "No similar products found."

    discount_offer = ""
    if customer.get("loyalty_level") in ["Gold", "Platinum"]:
        discount_offer = "As a valued {loyalty_level} customer, we’re offering you a 15% discount on your next purchase or free shipping on this order to ensure your satisfaction."
    elif customer.get("loyalty_level") == "Silver":
        discount_offer = "As a Silver customer, we’re happy to offer a 10% discount on a replacement item or your next purchase."
    else:
        discount_offer = "We’d love to offer you a 5% discount on your next purchase to show our appreciation."

    if complaint:
        prompt = (
            f"Customer {customer['name']} (email: {customer['email']}, loyalty: {customer['loyalty_level']}) "
            f"has a follow-up complaint about their purchase of style {style}: {product['description']} "
            f"(price: ${product['price']}, color: {product['color']}, fit: {product['fit']}, occasion: {product['occasion']}). "
            f"Their complaint: {complaint}. "
            f"Their purchase history: {json.dumps(customer['purchase_history'])}. "
            f"Sales stats for this style: total orders {sales_stats['total_count']}, "
            f"with statuses {json.dumps(sales_stats['status_counts'])}. "
            f"Suggested alternative products in their preferred category ({customer['preferred_category']}): {similar_products_text}. "
            f"Generate a polite, empathetic, and persuasive email response addressing their specific complaint. "
            f"Acknowledge their issue, apologize sincerely, and offer tailored solutions such as a replacement, "
            f"{discount_offer}, or a return option. Suggest alternative products from the provided list that align with their preferences. "
            f"Emphasize the quality and benefits of the product they purchased and how the suggested alternatives meet their needs. "
            f"Encourage them to continue the conversation if they’re still unsatisfied and highlight that their feedback is valued. "
            f"Use a friendly, professional, and verbose tone to retain them as a customer."
        )
    else:
        prompt = (
            f"Customer {customer['name']} (email: {customer['email']}, loyalty: {customer['loyalty_level']}) "
            f"has requested to cancel their purchase of style {style}: {product['description']} "
            f"(price: ${product['price']}, color: {product['color']}, fit: {product['fit']}, occasion: {product['occasion']}). "
            f"Their purchase history: {json.dumps(customer['purchase_history'])}. "
            f"Sales stats for this style: total orders {sales_stats['total_count']}, "
            f"with statuses {json.dumps(sales_stats['status_counts'])}. "
            f"Suggested alternative products in their preferred category ({customer['preferred_category']}): {similar_products_text}. "
            f"Generate a polite, persuasive email message to convince them not to cancel. "
            f"Suggest alternatives from the provided list that align with their preferences. "
            f"Offer incentives like {discount_offer}. Highlight the benefits of the purchased product, "
            f"such as quality, style, and suitability for their needs. Mention that they can return the product if not satisfied, "
            f"but encourage them to give it a chance. Use a friendly, professional, and verbose tone to retain them as a customer."
        )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "grok-3",
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
        # Save the response to conversation history
        if agent:
            agent.save_conversation_turn(customer_id, "assistant", message)
        return f"Generated message to send to {customer['email']}:\n\n{message}"
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