import json
from couchbase.cluster import Cluster
from couchbase.auth import PasswordAuthenticator
from couchbase.options import ClusterOptions
from couchbase.exceptions import CouchbaseException
import couchbase.subdocument as SD

csv_file = r"C:\Users\ragde\Desktop\customers.json"

# Load JSON data from file
with open(csv_file, 'r') as file:
    customers = json.load(file)

# Couchbase connection details
cluster_connection_string = 'couchbase://localhost'  # Replace with your cluster IP or hostname
username = 'Administrator'  # Replace with your Couchbase username
password = 'Administrator'      # Replace with your Couchbase password
bucket_name = 'customer_data'
scope_name = '_default'
collection_name = '_default'

# Connect to Couchbase cluster
auth = PasswordAuthenticator(username, password)
cluster = Cluster(cluster_connection_string, ClusterOptions(auth))
#cluster.wait_until_ready(timeout=30)  # Wait for cluster to be ready

# Get bucket and collection
bucket = cluster.bucket(bucket_name)
collection = bucket.scope(scope_name).collection(collection_name)

# Upsert each customer document into Couchbase
for customer in customers:
    customer_id = customer['customer_id']
    try:
        # Upsert document with customer_id as the key
        collection.upsert(customer_id, customer)
        print(f"Successfully upserted customer {customer_id}")
    except CouchbaseException as e:
        print(f"Error upserting customer {customer_id}: {e}")

# Optional: Verify data insertion by querying a few documents
try:
    query = f"SELECT * FROM `{bucket_name}`.`{scope_name}`.`{collection_name}` LIMIT 5"
    result = cluster.query(query)
    for row in result:
        print(f"Retrieved document: {row}")
except CouchbaseException as e:
    print(f"Error querying documents: {e}")

# Disconnect (optional, as Python will clean up on script exit)
# cluster.disconnect()