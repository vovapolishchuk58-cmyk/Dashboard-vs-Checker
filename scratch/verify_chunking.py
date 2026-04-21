import asyncio
import time
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from checker import check_products
from product_data import load_products

async def test_chunking():
    print("Starting chunking test...")
    # Set a very short runtime to see if it stops
    start = time.time()
    await check_products(max_runtime=5) # 5 seconds limit
    end = time.time()
    
    print(f"Test finished in {end - start:.2f} seconds.")
    print("Check logs above to see if it stopped after some items.")

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(test_chunking())
