import json
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from product_data import supabase, save_products

PRODUCTS_FILE = "tracked_products.json"

def reimport():
    load_dotenv()
    
    if not os.path.exists(PRODUCTS_FILE):
        print(f"Error: {PRODUCTS_FILE} not found.")
        return

    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        new_products = json.load(f)

    print(f"Loaded {len(new_products)} products from JSON.")

    # 1. WIPE DATABASE
    print("Wiping current database table 'products'...")
    try:
        # We use a filter that matches all rows (e.g., id is not null)
        # Note: If RLS is enabled without a policy allowing delete, this might fail.
        # But based on migration_script.py, we have write access.
        response = supabase.table("products").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print(f"Wipe complete. Rows deleted: {len(response.data) if response.data else 'Check Table'}")
    except Exception as e:
        print(f"Warning during wipe: {e}")
        print("Continuing to import (will upsert on conflict if wipe was partial)...")

    # 2. IMPORT DATA
    print("Starting import...")
    # save_products already handles batches and normalization
    # but we should ensure 'id' is NOT sent if we want fresh UUIDs, 
    # unless the user wants to keep the IDs from the JSON.
    # Looking at the JSON keys from earlier, it DID include 'id'.
    # To avoid conflict or confusion, we'll strip 'id' from the new products
    # so Supabase generates new ones, OR we keep them if they are valid.
    
    for p in new_products:
        if 'id' in p:
            del p['id'] # Let Supabase generate new IDs to avoid UUID conflicts
    
    # Batch saving (save_products takes a list)
    # We'll batch them in groups of 50 for stability
    batch_size = 50
    for i in range(0, len(new_products), batch_size):
        batch = new_products[i:i + batch_size]
        print(f"Importing batch {i//batch_size + 1}/{(len(new_products)-1)//batch_size + 1}...")
        save_products(batch)

    print("Re-import finished successfully!")

if __name__ == "__main__":
    reimport()
