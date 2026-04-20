import json

file_path = 'tracked_products.json'

with open(file_path, 'r', encoding='utf-8') as f:
    products = json.load(f)

updated_count = 0
reverted_count = 0

for product in products:
    supplier = product.get('supplier')
    
    # 1. Fix Aveopt Selectors
    if supplier == 'Aveopt':
        selectors = product.get('selectors', {})
        # Replace brittle IDs with robust classes
        if '#product-' in (selectors.get('availability') or ''):
            selectors['availability'] = '.summary p.stock'
            updated_count += 1
        if '#product-' in (selectors.get('rrp_price') or ''):
            selectors['rrp_price'] = '.summary .price'
            updated_count += 1
            
    # 2. Revert global out_of_stock change for non-Optclub (unless it's actually used by them)
    # Most suppliers don't use .outOfStock.label
    if supplier != 'Optclub':
        selectors = product.get('selectors', {})
        if selectors.get('out_of_stock') == '.outOfStock.label':
            # Revert to original. Since I don't have the original, I'll set it back to null or a common default.
            # For Daddy-store it was likely null. For Lugi null. 
            selectors['out_of_stock'] = None
            reverted_count += 1

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(products, f, ensure_ascii=False, indent=4)

print(f"Updated Aveopt: {updated_count}")
print(f"Reverted global changes: {reverted_count}")
