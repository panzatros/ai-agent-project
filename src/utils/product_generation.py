import json
import random
from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.exceptions import CouchbaseException
from datetime import timedelta

# Define description templates and attributes
templates = {
    "AN": [
        "Crafted from {material}, this {style} {color} top offers a {fit} fit, perfect for {occasion}.",
        "A {color} {style} shirt made with {material}, designed for {fit} comfort and {occasion} wear."
    ],
    "BL": [
        "These {color} {style} pants, made from {material}, provide a {fit} fit for {occasion}.",
        "Comfortable {material} {color} bottoms with a {style} design, ideal for {occasion}."
    ],
    "SET": [
        "A stylish {color} {style} set crafted from {material}, offering a {fit} fit for {occasion}.",
        "This {material} {color} set features a {style} look, perfect for {occasion}."
    ]
}

attributes = {
    "material": ["cotton", "polyester", "linen", "denim", "silk"],
    "color": ["black", "navy", "white", "red", "grey"],
    "style": ["casual", "modern", "classic", "trendy", "athletic"],
    "fit": ["slim", "relaxed", "tailored", "loose", "fitted"],
    "occasion": ["everyday wear", "special occasions", "casual outings", "professional settings", "active lifestyles"]
}

# Price ranges by category
price_ranges = {
    "Apparel": (20.00, 50.00),
    "Bottoms": (30.00, 70.00),
    "Sets": (50.00, 120.00)
}

# Function to determine category from style
def get_category(style):
    if style.startswith("AN"):
        return "Apparel"
    elif style.startswith("BL"):
        return "Bottoms"
    else:
        return "Sets"

# Function to generate a random description and product details
def generate_product_details(style):
    category = get_category(style)
    category_key = style[:2] if style.startswith(("AN", "BL")) else "SET"
    template = random.choice(templates[category_key])
    
    # Select random attributes
    material = random.choice(attributes["material"])
    color = random.choice(attributes["color"])
    style = random.choice(attributes["style"])
    fit = random.choice(attributes["fit"])
    occasion = random.choice(attributes["occasion"])
    
    # Generate description
    description = template.format(
        material=material,
        color=color,
        style=style,
        fit=fit,
        occasion=occasion
    )
    
    # Generate random price within category range
    min_price, max_price = price_ranges[category]
    price = round(random.uniform(min_price, max_price), 2)
    
    return {
        "description": description,
        "price": price,
        "material": material,
        "color": color,
        "fit": fit,
        "occasion": occasion
    }

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
    for style in products.keys():
        product_details = generate_product_details(style)
        product_doc = {
            "style": style,
            "category": get_category(style),
            "description": product_details["description"],
            "price": product_details["price"],
            "material": product_details["material"],
            "color": product_details["color"],
            "fit": product_details["fit"],
            "occasion": product_details["occasion"]
        }
        result = collection.upsert(style, product_doc)
        print(f"Successfully upserted product {style} with CAS: {result.cas}")

except CouchbaseException as e:
    print("Couchbase error:", e)
except Exception as e:
    print("Error:", e)