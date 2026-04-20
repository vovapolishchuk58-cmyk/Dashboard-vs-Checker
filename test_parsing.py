import sys
import os

# Add current directory to path so we can import checker
sys.path.append(os.getcwd())

from checker import parse_product_logic, clean_price

def test_parsing():
    print("--- Testing clean_price ---")
    assert clean_price("1 250,50 грн") == 1250.50
    assert clean_price("1,250.99") == 1250.99
    assert clean_price("₴ 500") == 500.0
    assert clean_price("Price: 100.00") == 100.00
    assert clean_price("1.500,00") == 1500.00
    print("✅ clean_price tests passed")

    print("\n--- Testing Selectors ---")
    html_selector = """
    <html>
        <div class="price">799.00</div>
        <div class="availability">In Stock</div>
    </html>
    """
    selectors = {"rrp_price": ".price", "availability": ".availability"}
    res = parse_product_logic(html_selector, "http://test.com", selectors, "Test")
    assert res["price"] == 799.0
    assert res["is_available"] == True
    assert res["used_method"] == "selector"
    print("✅ Selector parsing passed")

    print("\n--- Testing Multi-Selectors ---")
    selectors_list = {"rrp_price": [".wrong", ".price"], "availability": [".absent", ".availability"]}
    res = parse_product_logic(html_selector, "http://test.com", selectors_list, "Test")
    assert res["price"] == 799.0
    assert res["is_available"] == True
    print("✅ Multi-selector parsing passed")

    print("\n--- Testing Out of Stock Selector ---")
    html_out = """
    <html>
        <div class="sold-out">SADLY SOLD OUT</div>
    </html>
    """
    selectors_out = {"out_of_stock": ".sold-out"}
    res = parse_product_logic(html_out, "http://test.com", selectors_out, "Test")
    assert res["is_available"] == False
    assert "SADLY SOLD OUT" in res["availability_text"]
    print("✅ Out of stock selector parsing passed")

    print("\n--- Testing JSON-LD Fallback ---")

    html_json_ld = """
    <html>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "Test Product",
            "image": "http://test.com/img.jpg",
            "offers": {
                "@type": "Offer",
                "price": "1234.56",
                "availability": "https://schema.org/InStock"
            }
        }
        </script>
    </html>
    """
    res = parse_product_logic(html_json_ld, "http://test.com", {"rrp_price": ".missing"}, "Test")
    assert res["price"] == 1234.56
    assert res["is_available"] == True
    assert res["used_method"] == "json-ld"
    assert res["image_url"] == "http://test.com/img.jpg"
    print("✅ JSON-LD fallback passed")

    print("\n--- Testing Meta Tags Fallback ---")
    html_meta = """
    <html>
        <meta property="product:price:amount" content="99.99">
        <meta property="og:availability" content="instock">
        <meta property="og:image" content="/path/to/img.webp">
    </html>
    """
    res = parse_product_logic(html_meta, "http://test.com", {"rrp_price": ".missing"}, "Test")
    assert res["price"] == 99.99
    assert res["is_available"] == True
    assert res["used_method"] == "meta"
    assert res["image_url"] == "http://test.com/path/to/img.webp"
    print("✅ Meta tags fallback passed")

    print("\n--- Testing Heuristic Fallback ---")
    html_heuristic = """
    <html>
        <body>
            <div>The current price is ₴ 450.00 for this item.</div>
        </body>
    </html>
    """
    res = parse_product_logic(html_heuristic, "http://test.com", {"rrp_price": ".missing"}, "Test")
    assert res["price"] == 450.0
    assert res["used_method"] == "heuristic"
    print("✅ Heuristic fallback passed")

if __name__ == "__main__":
    try:
        test_parsing()
        print("\n🚀 ALL TESTS PASSED!")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED!")
        raise e
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise e
