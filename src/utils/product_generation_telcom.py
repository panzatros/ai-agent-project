import json
import random
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.exceptions import CouchbaseException
from datetime import timedelta

# Define description templates and attributes for telecom products
templates = {
    "DP": [  # Data Plans
        "Experience blazing-fast connectivity with this {data_type} data plan offering {data_limit} of high-speed data, perfect for {usage_type}. Includes {network_type} coverage and {additional_feature} for seamless usage.",
        "Stay connected with our {data_type} plan, providing {data_limit} of data on a {network_type} network. Ideal for {usage_type}, with {additional_feature} to enhance your experience."
    ],
    "MP": [  # Mobile Phones
        "The {brand} {model} smartphone, featuring a {screen_size}-inch display, {storage} storage, and {camera_specs} camera. Perfect for {usage_type}, with {additional_feature} and a {battery_life} battery.",
        "Discover the {brand} {model}, a sleek device with {storage} of storage, a {screen_size}-inch screen, and {camera_specs} camera. Built for {usage_type}, it includes {additional_feature} and {battery_life} battery life."
    ],
    "AC": [  # Accessories
        "Enhance your device with this {accessory_type} in {color}, designed for {compatibility}. Features {additional_feature} and is ideal for {usage_type}.",
        "This {color} {accessory_type} is crafted for {compatibility}, offering {additional_feature}. Perfect for {usage_type} to complement your telecom experience."
    ]
}

attributes = {
    "data_type": ["unlimited", "prepaid", "postpaid", "family-shared", "business"],
    "data_limit": ["5GB", "10GB", "20GB", "50GB", "unlimited"],
    "network_type": ["4G LTE", "5G", "5G Ultra Wideband"],
    "brand": ["Apple", "Samsung", "Google", "OnePlus", "Xiaomi"],
    "model": ["iPhone 14 Pro", "Galaxy S23", "Pixel 7", "Nord 3", "Mi 13"],
    "screen_size": ["6.1", "6.4", "6.7", "6.8", "7.0"],
    "storage": ["128GB", "256GB", "512GB", "1TB"],
    "camera_specs": ["12MP dual", "48MP triple", "50MP quad", "108MP advanced"],
    "battery_life": ["long-lasting", "all-day", "extended", "up to 24 hours"],
    "accessory_type": ["wireless charger", "protective case", "Bluetooth earbuds", "screen protector", "charging cable"],
    "color": ["black", "silver", "blue", "red", "white"],
    "compatibility": ["universal", "iPhone models", "Samsung Galaxy", "most Android devices"],
    "additional_feature": ["priority customer support", "water resistance", "fast charging", "noise cancellation", "unlimited cloud backup"],
    "usage_type": ["streaming and gaming", "work and productivity", "social media", "everyday use", "travel"]
}

# Price ranges by category
price_ranges = {
    "Data Plans": (10.00, 80.00),
    "Mobile Phones": (299.00, 1499.00),
    "Accessories": (9.99, 99.99)
}

# Additional attributes for sales
stock_status = ["in stock", "low stock", "out of stock"]
warranty_options = ["1-year limited", "2-year extended", "90-day standard"]
rating_options = [3.5, 3.8, 4.0, 4.2, 4.5, 4.8, 5.0]

# Function to determine category from style
def get_category(style):
    if style.startswith("DP"):
        return "Data Plans"
    elif style.startswith("MP"):
        return "Mobile Phones"
    elif style.startswith("AC"):
        return "Accessories"
    else:
        return "Unknown"

# Function to generate a random description and product details
def generate_product_details(style):
    category = get_category(style)
    category_key = style[:2] if style.startswith(("DP", "MP", "AC")) else "DP"
    template = random.choice(templates[category_key])
    
    # Select random attributes based on category
    if category == "Data Plans":
        selected_attributes = {
            "data_type": random.choice(attributes["data_type"]),
            "data_limit": random.choice(attributes["data_limit"]),
            "network_type": random.choice(attributes["network_type"]),
            "additional_feature": random.choice(attributes["additional_feature"]),
            "usage_type": random.choice(attributes["usage_type"])
        }
    elif category == "Mobile Phones":
        selected_attributes = {
            "brand": random.choice(attributes["brand"]),
            "model": random.choice(attributes["model"]),
            "screen_size": random.choice(attributes["screen_size"]),
            "storage": random.choice(attributes["storage"]),
            "camera_specs": random.choice(attributes["camera_specs"]),
            "battery_life": random.choice(attributes["battery_life"]),
            "additional_feature": random.choice(attributes["additional_feature"]),
            "usage_type": random.choice(attributes["usage_type"])
        }
    else:  # Accessories
        selected_attributes = {
            "accessory_type": random.choice(attributes["accessory_type"]),
            "color": random.choice(attributes["color"]),
            "compatibility": random.choice(attributes["compatibility"]),
            "additional_feature": random.choice(attributes["additional_feature"]),
            "usage_type": random.choice(attributes["usage_type"])
        }
    
    # Generate description
    description = template.format(**selected_attributes)
    
    # Generate random price within category range
    min_price, max_price = price_ranges[category]
    price = round(random.uniform(min_price, max_price), 2)
    
    # Generate additional sales attributes
    stock = random.choice(stock_status)
    warranty = random.choice(warranty_options)
    rating = random.choice(rating_options)
    
    # Merge attributes
    product_details = {
        "description": description,
        "price": price,
        "stock_status": stock,
        "warranty": warranty,
        "customer_rating": rating,
        **selected_attributes
    }
    
    return product_details

# Path to the JSON file
csv_file = r"C:\Users\ragde\Desktop\products.json"

# Load the products dataset
try:
    with open(csv_file, "r") as file:
        products = json.load(file)
except FileNotFoundError:
    print("Error: products.json not found")
    exit(1)

# Connect to Couchbase
try:
    cluster = Cluster('couchbase://localhost', ClusterOptions(
        PasswordAuthenticator('Administrator', 'Administrator')  # Replace with your credentials
    ))
    cluster.wait_until_ready(timedelta(seconds=5))

    bucket = cluster.bucket('products')  # Use 'products' bucket
    collection = bucket.default_collection()  # Default collection

    # Upsert each product as a document
    for style in products.get("style_status_counts", {}).keys():
        product_details = generate_product_details(style)
        product_doc = {
            "style": style,
            "category": get_category(style),
            **product_details
        }
        result = collection.upsert(style, product_doc)
        print(f"Successfully upserted product {style} with CAS: {result.cas}")

except CouchbaseException as e:
    print("Couchbase error:", e)
except Exception as e:
    print("Error:", e)