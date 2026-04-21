import sys
import os
import asyncio
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from product_data import load_products, save_products
from checker import check_products

DOMAIN_MAP = {
    'drop-primaveo.com.ua': 'Primaveo',
    'www.aveopt.com.ua': 'Aveopt',
    'optclub.com.ua': 'OptClub',
    'daddy-store.com.ua': 'Daddy Store',
    'lugi.com.ua': 'Lugi',
    'hanert.com.ua': 'Hanert'
}

def repair_suppliers():
    print("[REPAIR] Loading products for supplier restoration...")
    products = load_products()
    repaired_count = 0
    
    for p in products:
        url = p.get('url')
        if not url:
            continue
        
        domain = url.split('/')[2]
        expected_supplier = DOMAIN_MAP.get(domain)
        
        # If supplier is missing or generic default
        if expected_supplier and (not p.get('supplier') or p.get('supplier') in ('Не вказано', ' ')):
            p['supplier'] = expected_supplier
            repaired_count += 1
            
    if repaired_count > 0:
        print(f"[REPAIR] Saving {repaired_count} repaired suppliers to Supabase...")
        save_products(products)
    else:
        print("[REPAIR] No suppliers needed repair.")

async def repair_names():
    print("[REPAIR] Starting re-parse for products with missing names...")
    # running check_products will now automatically repair names 
    # because of the new 'auto-extract name' logic in checker.py
    # and it will skip recently checked items unless we force it.
    
    # Actually, we want to force re-checking the corrupted ones.
    # We can do this by setting their last_checked_iso to a very old date.
    
    products = load_products()
    forced_count = 0
    for p in products:
        # Шукаємо тих, у кого злетіло ім'я АБО колір
        is_bad_name = p.get('product_name') in ('Невідомий товар', ' ', '')
        is_bad_color = p.get('color') in ('—', ' ', '', None)
        
        if is_bad_name or is_bad_color:
            p['last_checked_iso'] = '2000-01-01T00:00:00'
            forced_count += 1
            
    if forced_count > 0:
        print(f"[REPAIR] Resetting check date for {forced_count} corrupted products...")
        save_products(products)
        print("[REPAIR] Triggering checker. This may take a few minutes...")
        await check_products(max_runtime=300) # Give it 5 mins to repair as many as possible
    else:
        print("[REPAIR] No corrupted product names found.")

if __name__ == "__main__":
    load_dotenv()
    repair_suppliers()
    asyncio.run(repair_names())
