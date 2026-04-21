import os
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def test_telegram():
    if not TOKEN or not CHAT_ID:
        print("❌ Помилка: TELEGRAM_BOT_TOKEN або TELEGRAM_CHAT_ID не знайдено в .env")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "🚀 **Тестове повідомлення від системи моніторингу товарів!**\n\nЯкщо ви бачите це повідомлення, значить ваш Telegram бот налаштований правильно і готовий надсилати сповіщення про зміну цін та наявності.",
        "parse_mode": "Markdown"
    }

    print(f"Відправка повідомлення в чат {CHAT_ID}...")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                print("✅ Успіх! Повідомлення відправлено.")
            else:
                text = await response.text()
                print(f"❌ Помилка Telegram API: {response.status} - {text}")

if __name__ == "__main__":
    asyncio.run(test_telegram())
