import json
import os

file_path = 'tracked_products.json'

if not os.path.exists(file_path):
    print(f"Error: {file_path} not found")
    exit(1)

with open(file_path, 'r', encoding='utf-8') as f:
    products = json.load(f)

count = 0
for product in products:
    supplier = product.get('supplier')
    # Optclub uses this selector, others don't.
    # Aveopt was already fixed manually in the previous step.
    if supplier != 'Optclub' and supplier != 'Aveopt':
        selectors = product.get('selectors', {})
        if selectors.get('out_of_stock') == '.outOfStock.label':
            selectors['out_of_stock'] = None
            count += 1

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(products, f, ensure_ascii=False, indent=4)

print(f"Cleanup complete. Reverted {count} entries for non-Optclub suppliers.")
