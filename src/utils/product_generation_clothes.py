import json
import random
from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.exceptions import CouchbaseException
from datetime import timedelta

# Define description templates and attributes for telecom products
templates = {
    "DP": [  # Data Plans
        "Experience blazing-fast connectivity with this {data_amount} {network_type} data plan, perfect for {usage_type}. Includes {features} for an enhanced user experience.",
        "Stay connected with our {data_amount} {network_type} plan, designed for {usage_type}. Enjoy {features} and reliable coverage for all your needs."
    ],
    "MP": [  # Mobile Phones
        "The {brand} {model} smartphone, featuring a {display_size}-inch display, {storage} storage, and {features}. Ideal for {usage_type}, this device offers {color} elegance and top-tier performance.",
        "Discover the {brand} {model}, a {color} mobile phone with {storage} storage, {display_size}-inch screen, and {features}. Perfect for {usage_type} and built for reliability."
    ],
    "AC": [  # Accessories
        "Enhance your device with this {color} {accessory_type} from {brand}. Designed for {compatibility}, it offers {features} and is perfect for {usage_type}.",
        "This {brand} {color} {accessory_type} is crafted for {compatibility}, featuring {features}. Ideal for {usage_type}, it combines style and functionality."
    ]
}

attributes = {
    "data_amount": ["1GB", "5GB", "10GB", "20GB", "50GB", "Unlimited"],
    "network_type": ["4G", "5G"],
    "brand": ["Samsung", "Apple", "Xiaomi", "OnePlus", "Google", "Sony"],
    "model": ["Galaxy S23", "iPhone 15", "Redmi Note 12", "Nord 3", "Pixel 8", "Xperia 5"],
    "display_size": ["6.1", "6.7", "6.4", "6.8", "6.2"],
    "storage": ["64GB", "128GB", "256GB", "512GB", "1TB"],
    "color": ["Midnight Black", "Starlight White", "Sky Blue", "Emerald Green", "Phantom Grey"],
    "accessory_type": ["wireless earbuds", "fast charger", "protective case", "screen protector", "smartwatch"],
    "compatibility": ["universal compatibility", "iOS devices", "Android devices", "specific models"],
    "features": [
        "unlimited calls and texts", "high-speed streaming", "advanced noise cancellation", 
        "water-resistant design", "long-lasting battery", "wireless charging support",
        "AMOLED display", "dual SIM support", "5G connectivity", "shockproof protection"
    ],
    "usage_type": ["daily browsing", "gaming", "streaming", "professional use", "travel", "fitness tracking"]
}

# Price ranges by category
price_ranges = {
    "Data Plans": (10.00, 80.00),
    "Mobile Phones": (200.00, 1500.00),
    "Accessories": (15.00, 200.00)
}

# Function to determine category from style
def get_category(style):
    if style.startswith("DP"):
        return "Data Plans"
    elif style.startswith("MP"):
        return "Mobile Phones"
    else:  # AC
        return "Accessories"

# Function to generate a random description and product details
def generate_product_details(style):
    category = get_category(style)
    category_key = style[:2] if style.startswith(("DP", "MP", "AC")) else "AC"
    template = random.choice(templates[category_key])
    
    # Select random attributes based on category
    if category == "Data Plans":
        data_amount = random.choice(attributes["data_amount"])
        network_type = random.choice(attributes["network_type"])
        features = ", ".join(random.sample(attributes["features"], 2))  # Pick 2 features
        usage_type = random.choice(attributes["usage_type"])
        description = template.format(
            data_amount=data_amount,
            network_type=network_type,
            features=features,
            usage_type=usage_type
        )
        product_doc = {
            "description": description,
            "data_amount": data_amount,
            "network_type": network_type,
            "features": features.split(", "),
            "usage_type": usage_type
        }
    elif category == "Mobile Phones":
        brand = random.choice(attributes["brand"])
        model = random.choice(attributes["model"])
        display_size = random.choice(attributes["display_size"])
        storage = random.choice(attributes["storage"])
        color = random.choice(attributes["color"])
        features = ", ".join(random.sample(attributes["features"], 3))  # Pick 3 features
        usage_type = random.choice(attributes["usage_type"])
        description = template.format(
            brand=brand,
            model=model,
            display_size=display_size,
            storage=storage,
            color=color,
            features=features,
            usage_type=usage_type
        )
        product_doc = {
            "description": description,
            "brand": brand,
            "model": model,
            "display_size": display_size,
            "storage": storage,
            "color": color,
            "features": features.split(", "),
            "usage_type": usage_type
        }
    else:  # Accessories
        brand = random.choice(attributes["brand"])
        accessory_type = random.choice(attributes["accessory_type"])
        color = random.choice(attributes["color"])
        compatibility = random.choice(attributes["compatibility"])
        features = ", ".join(random.sample(attributes["features"], 2))  # Pick 2 features
        usage_type = random.choice(attributes["usage_type"])
        description = template.format(
            brand=brand,
            color=color,
            accessory_type=accessory_type,
            compatibility=compatibility,
            features=features,
            usage_type=usage_type
        )
        product_doc = {
            "description": description,
            "brand": brand,
            "accessory_type": accessory_type,
            "color": color,
            "compatibility": compatibility,
            "features": features.split(", "),
            "usage_type": usage_type
        }
    
    # Generate random price within category range
    min_price, max_price = price_ranges[category]
    price = round(random.uniform(min_price, max_price), 2)
    product_doc["price"] = price
    product_doc["category"] = category
    product_doc["style"] = style
    
    # Add sales-relevant fields
    product_doc["stock_quantity"] = random.randint(0, 100)  # Random stock quantity
    product_doc["warranty"] = random.choice(["1 year", "2 years", "6 months", "No warranty"])  # Warranty info
    product_doc["release_date"] = f"202{random.randint(3, 5)}-{random.randint(1, 12):02d}-01"  # Random release date
    
    return product_doc

# Path to the JSON file
json_file = r"C:\Users\ragde\Desktop\products.json"

# Load the products dataset
try:
    with open(json_file, "r") as file:
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
    for style in products.keys():
        product_doc = generate_product_details(style)
        result = collection.upsert(style, product_doc)
        print(f"Successfully upserted product {style} with CAS: {result.cas}")

except CouchbaseException as e:
    print("Couchbase error:", e)
except Exception as e:
    print("Error:", e)