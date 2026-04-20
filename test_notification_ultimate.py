import asyncio

def get_status_icon(supplier):
    return "🇮🇹" if "Primaveo" in supplier else "📊"

def format_test(event_type, p, last_price=None, new_price=None, last_avail=None, new_avail=None):
    url = p["url"]
    status_icon = get_status_icon(p["supplier"])
    
    if event_type == "price_change":
        diff = new_price - last_price
        percent_change = abs(diff / last_price * 100)
        price_icon = "⬆️" if diff > 0 else "⬇️"
        return (
            f"💰 <b>ЗМІНА ЦІНИ!</b> {price_icon}\n\n"
            f"📦 <b>{p.get('product_name')}</b>\n\n"
            f"Стара: {last_price:.2f} грн → Нова: {new_price:.2f} грн\n\n"
            f"Різниця: {diff:+.2f} грн ({percent_change:.1f}%)\n\n"
            f"🏪 Постачальник: {p.get('supplier', '—')}\n\n"
            f"🎨 Колір: {p.get('color', '—')}\n\n"
            f"🔗 <a href='{url}'>Посилання на товар</a>"
        )
    elif event_type == "avail_change":
        header = "🎉 <b>ЗНОВУ В НАЯВНОСТІ</b> 🟢" if new_avail else "⚠️ <b>ТОВАР ЗАКІНЧИВСЯ!</b> 🔴"
        return (
            f"{header}\n\n"
            f"📦 <b>{p.get('product_name')}</b>\n\n"
            f"🎨 Колір: {p.get('color', '—')}\n\n"
            f"🏪 Постачальник: {p.get('supplier', '—')}\n\n"
            f"🔗 <a href='{url}'>Посилання на товар</a>"
        )
    elif event_type == "new_product":
        header = "🆕 <b>НОВИЙ ТОВАР В БАЗІ!</b> 🟢"
        avail_text = "В наявності" if new_avail else "Немає в наявності"
        return (
            f"{header}\n\n"
            f"📦 <b>{p.get('product_name')}</b>\n\n"
            f"{status_icon} Статус: {avail_text}\n\n"
            f"🎨 Колір: {p.get('color', '—')}\n\n"
            f"💰 Ціна: {new_price:.2f} грн\n\n"
            f"🏪 Постачальник: {p.get('supplier', '—')}\n\n"
            f"🔗 <a href='{url}'>Посилання на товар</a>"
        )

async def run_final_test():
    scenarios = [
        ("price_change", {"product_name": "BAMBI FLASH", "supplier": "Optclub", "color": "сірий", "url": "url"}, 1643.0, 1669.0),
        ("price_change", {"product_name": "DEXON OPTIMA", "supplier": "Daddy-store", "color": "коричневий", "url": "url"}, 2999.0, 2799.0),
        ("avail_change", {"product_name": "Газова плита-обігрівач", "supplier": "Aveopt", "color": "чорний", "url": "url"}, None, None, True, False),
        ("avail_change", {"product_name": "Стільчик для годування Toti", "supplier": "Optclub", "color": "сірий", "url": "url"}, None, None, False, True),
        ("new_product", {"product_name": "Комп'ютерне крісло Primaveo", "supplier": "Primaveo", "color": "чорний", "url": "url"}, None, 2250.0, None, True)
    ]
    
    for i, (etype, p, lp, np, la, na) in enumerate(scenarios, 1):
        print(f"\n--- SCENARIO {i}: {etype.upper()} ---")
        print(format_test(etype, p, lp, np, la, na))
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(run_final_test())
