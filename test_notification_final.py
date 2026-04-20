import asyncio

async def test_all_scenarios():
    # Helper to simulate icon logic
    def get_status_icon(supplier):
        return "🇮🇹" if "Primaveo" in supplier else "📊"

    # Scenario 1: Price Change (Up)
    p_up = {
        "product_name": "Дитяча прогулянкова Коляска BAMBI FLASH",
        "supplier": "Optclub",
        "color": "сірий",
        "url": "https://example.com/bambi",
        "image_current": "https://example.com/bambi.jpg"
    }
    last_price = 1643.0
    new_price = 1669.0
    
    diff = new_price - last_price
    percent_change = abs(diff / last_price * 100)
    price_icon = "⬆️" if diff > 0 else "⬇️"
    
    msg_up = (
        f"💰 <b>ЗМІНА ЦІНИ!</b> {price_icon}\n\n"
        f"📦 <b>{p_up.get('product_name')}</b>\n\n"
        f"Стара: {last_price:.2f} грн → Нова: {new_price:.2f} грн\n\n"
        f"Різниця: {diff:+.2f} грн ({percent_change:.1f}%)\n\n"
        f"🏢 Постачальник: {p_up.get('supplier', '—')}\n\n"
        f"🎨 Колір: {p_up.get('color', '—')}\n\n"
        f"🔗 <a href='{p_up['url']}'>Посилання на товар</a>"
    )

    # Scenario 2: Price Change (Down)
    p_down = {
        "product_name": "Крісло комп'ютерне DEXON OPTIMA",
        "supplier": "Daddy-store",
        "color": "коричневий",
        "url": "https://example.com/dexon",
        "image_current": "https://example.com/dexon.jpg"
    }
    last_price_d = 2999.0
    new_price_d = 2799.0
    
    diff_d = new_price_d - last_price_d
    percent_d = abs(diff_d / last_price_d * 100)
    icon_d = "⬆️" if diff_d > 0 else "⬇️"
    
    msg_down = (
        f"💰 <b>ЗМІНА ЦІНИ!</b> {icon_d}\n\n"
        f"📦 <b>{p_down.get('product_name')}</b>\n\n"
        f"Стара: {last_price_d:.2f} грн → Нова: {new_price_d:.2f} грн\n\n"
        f"Різниця: {diff_d:+.2f} грн ({percent_d:.1f}%)\n\n"
        f"🏢 Постачальник: {p_down.get('supplier', '—')}\n\n"
        f"🎨 Колір: {p_down.get('color', '—')}\n\n"
        f"🔗 <a href='{p_down['url']}'>Посилання на товар</a>"
    )

    # Scenario 3: New Product (Primaveo)
    p_new = {
        "product_name": "Комп'ютерне крісло Primaveo",
        "supplier": "Primaveo",
        "color": "чорний",
        "availability_text": "В наявності",
        "url": "https://example.com/primaveo",
        "image_current": "https://example.com/primaveo.jpg"
    }
    price_n = 2250.0
    header = "🆕 <b>НОВИЙ ТОВАР В БАЗІ!</b> 🟢"
    status_icon = get_status_icon(p_new["supplier"])

    msg_new = (
        f"{header}\n\n"
        f"📦 <b>{p_new.get('product_name')}</b>\n\n"
        f"{status_icon} Статус: {p_new.get('availability_text', '—')}\n\n"
        f"🎨 Колір: {p_new.get('color', '—')}\n\n"
        f"💰 Ціна: {price_n:.2f} грн\n\n"
        f"🏢 Постачальник: {p_new.get('supplier', '—')}\n\n"
        f"🔗 <a href='{p_new['url']}'>Посилання на товар</a>"
    )

    print("="*20 + " SCENARIO 1: PRICE UP " + "="*20)
    print(msg_up)
    print("="*20 + " SCENARIO 2: PRICE DOWN " + "="*20)
    print(msg_down)
    print("="*20 + " SCENARIO 3: NEW PRODUCT " + "="*20)
    print(msg_new)

if __name__ == "__main__":
    asyncio.run(test_all_scenarios())
