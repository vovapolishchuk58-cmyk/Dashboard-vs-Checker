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
        # Запускаємо асинхронну функцію перевірки з лімітом часу (25 секунд)
        # Це дозволяє завершити запит до того, як cron-job.org або Vercel скинуть з'єднання (30-60с)
        asyncio.run(check_products(max_runtime=18))
        return jsonify({"status": "success", "message": "Checker triggered successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run()
