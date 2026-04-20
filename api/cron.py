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
        # Запускаємо асинхронну функцію перевірки
        asyncio.run(check_products())
        return jsonify({"status": "success", "message": "Checker triggered successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run()
