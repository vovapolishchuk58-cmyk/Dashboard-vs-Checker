import asyncio
import aiohttp
from unittest.mock import MagicMock, AsyncMock
import logging

# Mock constants from checker.py
TELEGRAM_BOT_TOKEN = "TEST_TOKEN"
TELEGRAM_CHAT_ID = "TEST_ID"

# Function to test (copied from checker.py with small adjustments for testing)
async def send_telegram_async_mock(session, message, photo_url=None):
    method = "sendPhoto" if photo_url else "sendMessage"
    print(f"DEBUG: Calling Telegram API using method: {method}")
    print(f"DEBUG: Payload would be:")
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "parse_mode": "HTML",
    }
    if photo_url:
        payload["photo"] = photo_url
        payload["caption"] = message[:1024]
    else:
        payload["text"] = message[:4096]
    
    print(payload)
    return True

async def test_formatting():
    # Test Data
    p_new = {
        "product_name": "Комп'ютерне крісло Primaveo з ергономічною спинкою",
        "supplier": "Primaveo",
        "color": "чорний",
        "availability_text": "В наявності",
        "image_current": "https://example.com/chair.jpg",
        "url": "https://example.com/item1"
    }
    new_price = 2250.0
    msg_parts = ["🆕 <b>НОВИЙ ТОВАР В БАЗІ!</b> 🟢"]
    url = p_new["url"]

    # Notification Logic (replicated from checker.py)
    header = msg_parts[0] if msg_parts else ""
    status_icon = "🇮🇹" if "Primaveo" in (p_new.get("supplier") or "") else "📊"
    
    full_message = (
        f"{header}\n\n"
        f"📦 <b>{p_new.get('product_name')}</b>\n\n"
        f"{status_icon} Статус: {p_new.get('availability_text', '—')}\n\n"
        f"🎨 Колір: {p_new.get('color', '—')}\n\n"
        f"💰 Ціна: {new_price:.2f} грн\n\n"
        f"🏢 Постачальник: {p_new.get('supplier', '—')}\n\n"
        f"🔗 <a href='{url}'>Посилання на товар</a>"
    )

    print("-" * 50)
    print("FORMATTED MESSAGE:")
    print(full_message)
    print("-" * 50)

    # Simulate sending
    await send_telegram_async_mock(None, full_message, photo_url=p_new.get('image_current'))

if __name__ == "__main__":
    asyncio.run(test_formatting())
