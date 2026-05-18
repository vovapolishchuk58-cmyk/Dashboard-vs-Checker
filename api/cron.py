# api/cron.py
import asyncio
from flask import Flask, jsonify
import sys
import os

# Додаємо кореневу директорію до шляху пошуку модулів
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from checker import check_products

app = Flask(__name__)

@app.route('/api/cron')
def trigger_checker():
    try:
        # Запускаємо асинхронну функцію перевірки з лімітом часу (8 секунд)
        # Використовуємо wait_for, щоб жорстко перервати завислі запити (наприклад, якщо сайт довго не відповідає)
        # 15 секунд гарантують, що cron-job.org не впаде по таймауту (30с).
        async def run_with_timeout():
            try:
                await asyncio.wait_for(check_products(max_runtime=8), timeout=15)
            except asyncio.TimeoutError:
                pass # Проігнорувати жорсткий таймаут, бо частина товарів вже збережена

        asyncio.run(run_with_timeout())
        return jsonify({"status": "success", "message": "Checker triggered successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run()
