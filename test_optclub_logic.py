import sys
import os
from bs4 import BeautifulSoup

# Add current directory to path
sys.path.append(os.getcwd())

from checker import parse_product_logic

def test_optclub_out_of_stock():
    print("--- Testing Optclub Out of Stock Logic ---")
    
    # Simulating HTML from browse subagent findings
    html_out = """
    <html>
        <body>
            <div class="fixContainer">
                <a class="price changePrice">878 грн.</a>
                <div class="quantity-block">Кількість</div>
                <a class="outOfStock label eChangeAvailable">Немає доступу</a>
            </div>
        </body>
    </html>
    """
    
    selectors = {
        "availability": ".eChangeAvailable",
        "rrp_price": ".price.changePrice",
        "out_of_stock": ".outOfStock.label"
    }
    
    url = "https://optclub.com.ua/ua/item/test-product/"
    res = parse_product_logic(html_out, url, selectors, "Optclub")
    
    print(f"Price: {res['price']}")
    print(f"Is Available: {res['is_available']}")
    print(f"Availability Text: {res['availability_text']}")
    print(f"Used Method: {res.get('used_method')}")
    
    assert res["price"] == 878.0
    assert res["is_available"] == False
    assert "Немає доступу" in res["availability_text"]
    
    print("✅ Optclub Out of Stock test passed!")

def test_heuristic_global_negative():
    print("\n--- Testing Heuristic Global Negative Search ---")
    
    # HTML with price but "out of stock" text somewhere on page, and FAILing selectors
    html_heuristic = """
    <html>
        <body>
            <div class="some-price">Price: 500 грн</div>
            <p>Вибачте, цього товару зараз немає доступу на складі.</p>
        </body>
    </html>
    """
    
    # We provide a failing selector to trigger heuristic
    selectors = {
        "availability": ".non-existent",
        "rrp_price": ".some-price"
    }
    
    res = parse_product_logic(html_heuristic, "http://test.com", selectors, "Test")
    
    print(f"Price: {res['price']}")
    print(f"Is Available: {res['is_available']}")
    print(f"Availability Text: {res['availability_text']}")
    
    assert res["price"] == 500.0
    assert res["is_available"] == False
    assert "Heuristic: Out of stock text detected" in res["availability_text"]
    
    print("✅ Heuristic Global Negative Search passed!")

if __name__ == "__main__":
    try:
        test_optclub_out_of_stock()
        test_heuristic_global_negative()
        print("\n🚀 ALL VERIFICATION TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        sys.exit(1)
