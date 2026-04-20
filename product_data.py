# product_data.py - Модуль для роботи з даними через Supabase
# ✅ ВИПРАВЛЕННЯ: Повна міграція з локального JSON файлу на Supabase.

import os
from datetime import datetime
from typing import Dict, List, Callable
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Ініціалізація Supabase клієнта
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ ПОПЕРЕДЖЕННЯ: Змінні оточення SUPABASE_URL або SUPABASE_KEY не знайдені.")
    supabase: Client = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def normalize_product_defaults(p: dict) -> dict:
    """
    Нормалізує продукт, додаючи всі необхідні поля зі значеннями за замовчуванням.
    """
    p = dict(p or {})

    # Основні поля
    p.setdefault("supplier", "Не вказано")
    p.setdefault("product_name", "Невідомий товар")
    p.setdefault("url", None)
    p.setdefault("category", "Не вказано")
    p.setdefault("color", "—")

    # Селектори (в Supabase це JSONB)
    sel = p.get("selectors")
    if not isinstance(sel, dict):
        sel = {}
    sel.setdefault("availability", None)
    sel.setdefault("rrp_price", None)
    sel.setdefault("out_of_stock", None)
    sel.setdefault("image", None)
    p["selectors"] = sel

    p.setdefault("manual_image_url", None)

    # image_current: якщо нема — беремо manual
    if p.get("image_current") is None:
        p["image_current"] = p.get("manual_image_url")

    # Поточний стан
    p.setdefault("availability_text", "—")
    p.setdefault("availability_code", "UNKNOWN")
    p.setdefault("price_current", None)
    p.setdefault("price_text", "—")
    p.setdefault("last_checked_iso", None)

    # Legacy
    p.setdefault("is_available_last", None)
    p.setdefault("price_last", None)
    p.setdefault("last_checked", None)
    
    # Видаляємо зайві поля, яких немає в таблиці (наприклад, id, якщо ми покладаємось на url)
    # Зберігаємо тільки те, що визначено в структурі таблиці + id, якщо він є.
    
    return p


def load_products_unlocked() -> List[Dict]:
    """Legacy обгортка; тепер все робиться без локальних локів."""
    return load_products()


def save_products_unlocked(products: List[Dict], create_backup: bool = True) -> None:
    """Legacy обгортка; тепер все робиться без локальних локів."""
    save_products(products)


def load_products() -> List[Dict]:
    """
    Завантажує продукти з бази даних Supabase.
    """
    if not supabase:
        print("❌ Supabase не налаштовано. Повертаємо порожній список.")
        return []

    try:
        response = supabase.table("products").select("*").execute()
        raw_products = response.data
        return [normalize_product_defaults(p) for p in raw_products]
    except Exception as e:
        print(f"❌ Помилка завантаження даних з Supabase: {e}")
        return []


def save_products(products: List[Dict]) -> None:
    """
    Зберігає (Upsert) продукти в базу даних Supabase.
    Для ідентифікації конфліктів використовується поле 'url'.
    """
    if not supabase:
        print("❌ Supabase не налаштовано. Збереження неможливе.")
        return

    if not products:
        return

    try:
        # Supabase Python client accepts a list of dictionaries for bulk insert/upsert
        # Remove empty string or None ids if present to let DB generate UUID if it's new
        clean_products = []
        for p in products:
            cp = normalize_product_defaults(p)
            # Filter out 'id' if None so it doesn't break UUID generation
            if 'id' in cp and not cp['id']:
                del cp['id']
            # Supabase error protection: ignore "created_at" in upsert if passing it
            if 'created_at' in cp:
                del cp['created_at']
                
            clean_products.append(cp)

        response = supabase.table("products").upsert(clean_products, on_conflict="url").execute()
        print(f"✓ Дані успішно збережено в Supabase ({len(response.data)} задіяних рядків)")
    except Exception as e:
        print(f"❌ Помилка збереження в Supabase: {e}")


def update_products_locked(mutator_fn: Callable[[List[Dict]], List[Dict]]) -> None:
    """
    Раніше використовувалось для створення блокування файлу (lock).
    В Supabase ми можемо просто отримати поточні дані, виконати мутатор та зберегти їх.
    """
    try:
        products = load_products()
        mutated_products = mutator_fn(products)
        save_products(mutated_products)
    except Exception as e:
         print(f"❌ Помилка під час update_products_locked: {e}")
