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

# Couchbase connection setup
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

def handle_cancellation(customer_id: str, style: str, api_key: str) -> str:
    logger.debug(f"Handling cancellation for customer_id: {customer_id}, style: {style}")
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

    prompt = (
        f"Customer {customer['name']} (email: {customer['email']}, loyalty: {customer['loyalty_level']}) "
        f"wants to cancel their purchase of style {style}: {product['description']} (price: ${product['price']}, "
        f"color: {product['color']}, fit: {product['fit']}, occasion: {product['occasion']}). "
        f"Their purchase history: {json.dumps(customer['purchase_history'])}. "
        f"Sales stats for this style: total orders {sales_stats['total_count']}, "
        f"with statuses {json.dumps(sales_stats['status_counts'])}. "
        f"Generate a polite, persuasive email message to convince them not to cancel. "
        f"Suggest alternatives from similar categories if possible, based on their history and preferences "
        f"(preferred category: {customer['preferred_category']}). Offer incentives like discounts or free shipping "
        f"if they are loyal customers. Mention that their feedback is valuable and that you would like to keep them as a customer. "
        f"Emphasize the benefits of the product they purchased, such as quality, style, and suitability for their needs. "
        f"Also, mention that they can return the product if they are not satisfied, but you hope they will reconsider "
        f"and give it a chance. Use a friendly and professional tone and make a very verbose response."
    )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "grok-3",  # Changed to test alternative model
            "messages": [{"role": "user", "content": prompt}]
        }
        logger.debug(f"Sending Grok API request in handle_cancellation: {json.dumps(payload, indent=2)}")
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        response_data = response.json()
        logger.debug(f"Grok API response in handle_cancellation: {json.dumps(response_data, indent=2)}")
        message = response_data["choices"][0]["message"]["content"]
        return f"Generated message to send to {customer['email']}:\n\n{message}"
    except requests.exceptions.HTTPError as e:
        error_response = e.response.json() if e.response else {}
        logger.error(f"HTTP error in handle_cancellation: {e.response.status_code} - {json.dumps(error_response, indent=2)}")
        return f"Error generating message: HTTP {e.response.status_code} - {json.dumps(error_response, indent=2)}"
    except Exception as e:
        logger.error(f"Error in handle_cancellation: {str(e)}")
        return f"Error generating message: {str(e)}"