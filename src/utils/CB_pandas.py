import pandas as pd
from datetime import timedelta
from couchbase.cluster import Cluster
from couchbase.auth import PasswordAuthenticator
from couchbase.options import ClusterOptions
from couchbase.exceptions import CouchbaseException

csv_file = r"c:\tools\jdtls\archive\Amazon_Sale_Report.csv"

# Step 1: Load and analyze the CSV
# Replace 'your_sales.csv' with your actual file path
df = pd.read_csv(csv_file)

if 'Style' not in df.columns or 'Status' not in df.columns:
    raise ValueError("CSV must have 'Style' and 'Status' columns.")
if 'sales_amount' not in df.columns:
    # Fallback: Compute sales_amount if needed (adjust column names based on your CSV)
    if 'Qty' in df.columns and 'Amount' in df.columns:
        df['sales_amount'] = df['Qty'] * df['Amount']
    else:
        raise ValueError("CSV must have 'sales_amount' or 'Qty' and 'Amount' columns to compute it.")

# Compute statistics
stats = {
    'total_sales': float(df['sales_amount'].sum()),
    'average_sales': float(df['sales_amount'].mean()),
    'min_sales': float(df['sales_amount'].min()),
    'max_sales': float(df['sales_amount'].max()),
    'entry_count': int(df['sales_amount'].count()),
    'style_status_counts': {}
}

# Group by Style and Status, count occurrences
style_status_counts = df.groupby(['Style', 'Status']).size().unstack(fill_value=0).to_dict('index')

# Build nested structure: {Style: {total_count: X, status_counts: {Status1: Y, Status2: Z, ...}}
for style, status_counts in style_status_counts.items():
    stats['style_status_counts'][str(style)] = {
        'total_count': int(sum(status_counts.values())),
        'status_counts': {str(k): int(v) for k, v in status_counts.items()}
    }
#print("Computed statistics:", stats)

# Step 2: Connect to Couchbase and cache the stats
try:
    # Connection details (adjust for your setup; use 'couchbases://' for TLS)
    cluster = Cluster('couchbase://localhost', ClusterOptions(
        PasswordAuthenticator('Administrator', 'Administrator')  # Replace with your credentials
    ))
    cluster.wait_until_ready(timedelta(seconds=5))

    bucket = cluster.bucket('sales_cache')  # Your created bucket
    collection = bucket.default_collection()  # Use default collection

    # Upsert the stats as a JSON document with key 'total_sales_stats'
    result = collection.upsert('total_sales_stats', stats)
    print("Successfully cached stats in Couchbase with CAS:", result.cas)

except CouchbaseException as e:
    print("Couchbase error:", e)
except Exception as e:
    print("Error:", e)