# checker.py - ВИПРАВЛЕНА ВЕРСІЯ

import asyncio
import aiohttp
import os
from datetime import datetime
import time
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import json

from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import logging
import random
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

from product_data import (
    load_products,
    update_products_locked,
    normalize_product_defaults,
)

# =========================================================================
# КОНФІГУРАЦІЯ
# =========================================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# ✅ NEW: Додано налаштування для сповіщень
NOTIFY_ON_FIRST_CHECK = True  # Сповіщати про товар при першій перевірці якщо є в наявності
NOTIFY_ON_AVAILABILITY_CHANGE = True  # Сповіщати при зміні наявності
NOTIFY_ON_PRICE_CHANGE = True  # Сповіщати при зміні ціни
MIN_PRICE_CHANGE_PERCENT = 1.0  # Мінімальна зміна ціни для сповіщення (%)

MAX_CONCURRENT_REQUESTS = 5
REQUEST_TIMEOUT = 30
CONNECTOR_LIMIT = 50
RATE_LIMIT_DELAY = 0.3

# Anti-ban
JITTER_RANGE = (0.2, 0.9)

MAX_RETRIES = 3
RETRY_STATUSES = {429, 403, 503, 520, 521, 522, 523, 524}
BACKOFF_BASE_SECONDS = 1.5
BACKOFF_MAX_SECONDS = 20.0

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
    "Gecko/20100101 Firefox/122.0",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://www.google.com/",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# =========================================================================
# HELPERS
# =========================================================================

def safe_get_text(element) -> Optional[str]:
    if element:
        return element.get_text(strip=True, separator=" ").replace("\xa0", " ")
    return None


def clean_price(price_text: str) -> Optional[float]:
    if not price_text:
        return None

    # Remove non-numeric characters except for delimiters
    cleaned = re.sub(r"[^\d,.]", "", price_text)

    # Handle cases like "1 250,50" -> "1250,50"
    if not cleaned:
        return None

    # Normalization logic:
    # 1. If both , and . are present, assume the last one is the decimal separator
    # 2. If only , is present and it looks like a decimal separator (at the end), replace with .
    # 3. If only . is present, leave it.
    
    if "," in cleaned and "." in cleaned:
        comma_idx = cleaned.rfind(",")
        dot_idx = cleaned.rfind(".")
        if comma_idx > dot_idx:
            # , is decimal
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # . is decimal
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # Check if it's thousands (e.g., 1,250) or decimal (e.g., 12,50)
        # In UA/EU, 12,50 is more common. 
        # If it's towards the end (length - 4), it's likely decimal.
        if len(cleaned) - cleaned.rfind(",") <= 3:
             cleaned = cleaned.replace(",", ".")
        else:
             cleaned = cleaned.replace(",", "")
             
    try:
        # Final pass to remove everything but digits and a single dot
        final_numeric = re.sub(r"[^\d.]", "", cleaned)
        if final_numeric.count(".") > 1:
            # Keep only the last dot
            parts = final_numeric.split(".")
            final_numeric = "".join(parts[:-1]) + "." + parts[-1]
        
        return float(final_numeric)
    except (ValueError, TypeError):
        return None



def format_price_text(price_value: Optional[float]) -> str:
    return f"{price_value:.2f} грн" if price_value is not None else "—"


def detect_blocking(html: Optional[str], status: int) -> bool:
    if status in (403, 429, 503):
        return True
    if not html:
        return False
    text_lower = html.lower()
    blocking_keywords = [
        "captcha", "cloudflare", "access denied",
        "blocked", "verify you are human", "attention required"
    ]
    return any(keyword in text_lower for keyword in blocking_keywords)

# =========================================================================
# ADAPTIVE DOMAIN DELAY
# =========================================================================

_last_request_time: Dict[str, float] = defaultdict(float)
_domain_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_domain_delay: Dict[str, float] = defaultdict(lambda: 3.0)
_domain_penalty: Dict[str, int] = defaultdict(int)


def _get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return "unknown"


async def _apply_domain_delay(url: str) -> None:
    domain = _get_domain(url)
    lock = _domain_locks[domain]

    async with lock:
        now = time.time()
        elapsed = now - _last_request_time[domain]

        base_delay = float(_domain_delay[domain])
        wait_needed = max(0.0, base_delay - elapsed)

        jitter = random.uniform(*JITTER_RANGE)
        wait_total = (wait_needed + jitter) if wait_needed > 0 else (jitter * 0.3)

        if wait_total > 0:
            await asyncio.sleep(wait_total)

        _last_request_time[domain] = time.time()


def _build_headers() -> Dict[str, str]:
    headers = dict(DEFAULT_HEADERS)
    headers["User-Agent"] = random.choice(USER_AGENTS)
    return headers


def _penalize_domain(url: str) -> None:
    domain = _get_domain(url)
    _domain_penalty[domain] += 1
    _domain_delay[domain] = min(15.0, 3.0 + _domain_penalty[domain] * 2.0)


def _reward_domain(url: str) -> None:
    domain = _get_domain(url)
    if _domain_penalty[domain] > 0:
        _domain_penalty[domain] -= 1
    _domain_delay[domain] = max(2.0, 3.0 + _domain_penalty[domain] * 2.0)


async def fetch_page_with_retry(
    session: aiohttp.ClientSession, url: str
) -> Tuple[Optional[str], int]:
    for attempt in range(MAX_RETRIES + 1):
        await _apply_domain_delay(url)
        headers = _build_headers()

        try:
            async with session.get(url, headers=headers) as resp:
                status = resp.status
                text = await resp.text(errors="ignore")

                blocked = detect_blocking(text, status)
                if status == 200 and not blocked:
                    _reward_domain(url)
                    return text, 200

                if status == 200 and blocked:
                    status = 403

                if status in RETRY_STATUSES:
                    _penalize_domain(url)

                if status in RETRY_STATUSES and attempt < MAX_RETRIES:
                    backoff = min(
                        BACKOFF_MAX_SECONDS,
                        (BACKOFF_BASE_SECONDS ** attempt) + random.uniform(0, 1.0),
                    )
                    logger.warning(
                        f"⚠️ {status} для {url} | retry {attempt+1}/{MAX_RETRIES} через {backoff:.1f}s"
                    )
                    await asyncio.sleep(backoff)
                    continue

                return None, status

        except asyncio.TimeoutError:
            _penalize_domain(url)
            if attempt < MAX_RETRIES:
                backoff = min(
                    BACKOFF_MAX_SECONDS,
                    (BACKOFF_BASE_SECONDS ** attempt) + random.uniform(0, 1.0),
                )
                logger.warning(
                    f"⏱️ Timeout для {url} | retry {attempt+1}/{MAX_RETRIES} через {backoff:.1f}s"
                )
                await asyncio.sleep(backoff)
                continue
            return None, 0

        except Exception as e:
            _penalize_domain(url)
            if attempt < MAX_RETRIES:
                backoff = min(
                    BACKOFF_MAX_SECONDS,
                    (BACKOFF_BASE_SECONDS ** attempt) + random.uniform(0, 1.0),
                )
                logger.warning(
                    f"❌ Помилка {url}: {e} | retry {attempt+1}/{MAX_RETRIES} через {backoff:.1f}s"
                )
                await asyncio.sleep(backoff)
                continue
            return None, 0

    return None, 0

# =========================================================================
# PARSING
# =========================================================================

def parse_product_logic(
    html: str, url: str, selectors: Dict, product_name: str
) -> Dict:
    soup = BeautifulSoup(html, "html.parser")
    result = {
        "is_available": None,
        "availability_text": None,
        "price": None,
        "price_text_raw": None,
        "image_url": None,
        "selector_error": None,
        "used_method": "selector", # Tracking which method succeeded
    }

    # --- 1. Extract JSON-LD (Schema.org) ---
    json_ld_data = {}
    try:
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Product":
                            json_ld_data = item
                            break
                elif data.get("@type") == "Product":
                    json_ld_data = data
                
                if json_ld_data:
                    break
            except Exception:
                continue
    except Exception:
        pass

    # --- 2. Extract Meta Tags ---
    meta_data = {}
    try:
        for meta in soup.find_all("meta"):
            prop = meta.get("property") or meta.get("name")
            if prop:
                meta_data[prop] = meta.get("content")
    except Exception:
        pass

    # --- 3. PRICE PARSING ---
    price_found = False
    price_sel = (selectors or {}).get("rrp_price")
    
    # Try Selectors (can be string or list)
    if price_sel:
        sels = [price_sel] if isinstance(price_sel, str) else price_sel
        for sel in sels:
            price_el = soup.select_one(sel)
            if price_el:
                p_text = safe_get_text(price_el)
                price_val = clean_price(p_text)
                if price_val:
                    result["price"] = price_val
                    result["price_text_raw"] = p_text
                    price_found = True
                    result["used_method"] = "selector"
                    break

    # Fallback to JSON-LD
    if not price_found and json_ld_data:
        offers = json_ld_data.get("offers")
        if offers:
            if isinstance(offers, list):
                offers = offers[0]
            p_val = offers.get("price")
            if p_val:
                result["price"] = clean_price(str(p_val))
                price_found = True
                result["used_method"] = "json-ld"

    # Fallback to Meta Tags
    if not price_found:
        m_price = meta_data.get("product:price:amount") or meta_data.get("og:price:amount")
        if m_price:
            result["price"] = clean_price(str(m_price))
            price_found = True
            result["used_method"] = "meta"

    # Last resort: Heuristic (search for price pattern near currency symbols)
    if not price_found:
        # Looking for numbers followed by грн or preceded by ₴
        patterns = [
            r"(\d[\d\s,.]*)\s*(?:грн|UAH|₴)",
            r"(?:грн|UAH|₴)\s*(\d[\d\s,.]*)",
        ]
        text_content = soup.get_text(separator=" ", strip=True)
        for pattern in patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                val = clean_price(match.group(1))
                if val and 10 < val < 1000000: # Sanity check for price
                    result["price"] = val
                    price_found = True
                    result["used_method"] = "heuristic"
                    break

    if not price_found and price_sel:
         result["selector_error"] = ("price", str(price_sel))

    # --- 4. AVAILABILITY PARSING ---
    avail_found = False
    avail_sel = (selectors or {}).get("availability")
    
    if avail_sel:
        sels = [avail_sel] if isinstance(avail_sel, str) else avail_sel
        for sel in sels:
            avail_el = soup.select_one(sel)
            if avail_el:
                text = safe_get_text(avail_el)
                if text:
                    result["availability_text"] = text
                    text_lower = text.lower()
                    negative_keywords = [
                        "немає", "out of stock", "закінчився",
                        "відсутній", "очікується", "нет в наличии", "sold out",
                        "немає доступу"
                    ]
                    is_negative = any(kw in text_lower for kw in negative_keywords)
                    result["is_available"] = not is_negative
                    avail_found = True
                    break

    # Check specific 'out_of_stock' selectors (even if avail_found from previous selectors)
    out_sel = (selectors or {}).get("out_of_stock")
    if out_sel:
        sels = [out_sel] if isinstance(out_sel, str) else out_sel
        for sel in sels:
            out_el = soup.select_one(sel)
            if out_el:
                result["is_available"] = False
                result["availability_text"] = safe_get_text(out_el) or "Out of Stock (Matched)"
                avail_found = True
                break

    # Fallback to JSON-LD

    if not avail_found and json_ld_data:
        offers = json_ld_data.get("offers")
        if offers:
            if isinstance(offers, list):
                offers = offers[0]
            avail_url = offers.get("availability")
            if avail_url:
                avail_str = str(avail_url).lower()
                result["is_available"] = "outofstock" not in avail_str
                result["availability_text"] = "В наявності (JSON-LD)" if result["is_available"] else "Немає в наявності (JSON-LD)"
                result["used_method"] = "json-ld"
                avail_found = True

    # Fallback to Meta Tags
    if not avail_found:
        m_avail = meta_data.get("product:availability") or meta_data.get("og:availability")
        if m_avail:
            result["is_available"] = any(x in str(m_avail).lower() for x in ["instock", "in stock", "є в наявності"])
            result["availability_text"] = "Meta: " + str(m_avail)
            avail_found = True

    if not avail_found and avail_sel:
        # If we didn't find availability but have a selector, mark as error unless we have a price
        # (Sometimes price existence implies availability)
        if not price_found:
            result["selector_error"] = ("availability", str(avail_sel))
        else:
            # Heuristic: if price exists and no "out of stock" text found globally
            # Final heuristic check: if price found, assume available unless keywords found in whole page
            neg_keywords = ['немає в наявності', 'немає доступу', 'out of stock', 'unavailable', 'sold out']
            page_text_lower = soup.get_text().lower()
            if any(k in page_text_lower for k in neg_keywords):
                result["is_available"] = False
                result["availability_text"] = "Немає в наявності (евристика)"
            else:
                result["is_available"] = True
                result["availability_text"] = "В наявності (евристика)"
            result["used_method"] = "heuristic_price"

    # --- 5. IMAGE PARSING ---
    img_sel = (selectors or {}).get("image")
    img_found = False
    
    if img_sel:
        sels = [img_sel] if isinstance(img_sel, str) else img_sel
        for sel in sels:
            img_el = soup.select_one(sel)
            if img_el:
                rel_url = None
                for attr in ("src", "data-src", "data-original", "srcset"):
                    if img_el.has_attr(attr) and img_el[attr]:
                        rel_url = img_el[attr].split()[0] if attr == "srcset" else img_el[attr]
                        break
                if rel_url:
                    result["image_url"] = urljoin(url, rel_url)
                    img_found = True
                    break

    # Fallback to JSON-LD
    if not img_found and json_ld_data:
        image = json_ld_data.get("image")
        if image:
            if isinstance(image, list):
                image = image[0]
            if isinstance(image, dict):
                image = image.get("url")
            if image:
                result["image_url"] = urljoin(url, image)
                img_found = True

    # Fallback to Meta Tags
    if not img_found:
        m_img = meta_data.get("og:image") or meta_data.get("twitter:image")
        if m_img:
            result["image_url"] = urljoin(url, m_img)
            img_found = True

    return result



async def get_product_data_async(
    session: aiohttp.ClientSession,
    executor: ThreadPoolExecutor,
    product: Dict
) -> Dict:
    url = product.get("url")
    selectors = product.get("selectors", {}) or {}
    name = product.get("product_name", "Невідомий товар")

    if not url:
        return {"status_code": 0, "error": "No URL", "data": None}

    html, status = await fetch_page_with_retry(session, url)
    if not html:
        return {"status_code": status, "error": f"Network/Blocked (status={status})", "data": None}

    loop = asyncio.get_event_loop()
    parsed_data = await loop.run_in_executor(
        executor, parse_product_logic, html, url, selectors, name
    )

    return {"status_code": 200, "error": None, "data": parsed_data}

# =========================================================================
# TELEGRAM
# =========================================================================

async def send_telegram_async(session: aiohttp.ClientSession, message: str, photo_url: Optional[str] = None) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("⚠️ Telegram не налаштовано - сповіщення пропущено")
        return

    # Use sendPhoto if photo_url is provided, otherwise sendMessage
    method = "sendPhoto" if photo_url else "sendMessage"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "parse_mode": "HTML",
    }

    if photo_url:
        payload["photo"] = photo_url
        payload["caption"] = message[:1024]  # Caption limit is 1024
    else:
        payload["text"] = message[:4096]
        payload["disable_web_page_preview"] = False

    try:
        async with session.post(url, json=payload) as resp:
            if resp.status == 200:
                logger.info(f"✅ Telegram ({method}): повідомлення надіслано")
            else:
                logger.error(f"❌ Telegram error ({method}): HTTP {resp.status}")
                error_text = await resp.text()
                logger.error(f"Response: {error_text[:200]}")
                
                # If sendPhoto failed, try falling back to plain message
                if photo_url:
                    logger.warning("⚠️ Спроба відправити без фото після помилки...")
                    await send_telegram_async(session, message, photo_url=None)
    except Exception as e:
        logger.error(f"❌ Telegram exception: {e}")


async def notify_selector_error(
    session: aiohttp.ClientSession,
    product_name: str,
    url: str,
    error_tuple: Tuple
) -> None:
    type_err, selector = error_tuple
    label = "Ціна" if type_err == "price" else "Наявність"

    msg = (
        f"⚠️ <b>ПОМИЛКА СЕЛЕКТОРА!</b>\n\n"
        f"🛒 <b>Товар:</b> <code>{product_name}</code>\n"
        f"❌ <b>Не знайдено:</b> {label}\n"
        f"🔍 <b>Селектор:</b> <code>{selector}</code>\n"
        f"🔗 <a href='{url}'>Перейти до товару</a>"
    )

    await send_telegram_async(session, msg)

# =========================================================================
# MAIN CHECK
# =========================================================================

def _merge_updates_into_products(products: List[Dict], updates_by_url: Dict[str, Dict]) -> List[Dict]:
    for p in products:
        url = p.get("url")
        if not url:
            continue
        upd = updates_by_url.get(url)
        if not upd:
            continue
        p.update(upd)
    return products


async def check_products() -> None:
    # ✅ FIX: asyncio.Lock objects are bound to an event loop.
    # Since run_checker() uses asyncio.run() repeatedly (new loop each cycle),
    # we must recreate domain locks per cycle to avoid "bound to a different event loop".
    _domain_locks.clear()
    _last_request_time.clear()

    # Отримуємо дані з Supabase
    products_snapshot = load_products()

    if not products_snapshot:
        logger.warning("Список порожній.")
        return

    logger.info(f"🚀 Початок перевірки {len(products_snapshot)} товарів...")

    connector = aiohttp.TCPConnector(limit=CONNECTOR_LIMIT, ssl=False)
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    updates_by_url: Dict[str, Dict] = {}

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        with ThreadPoolExecutor() as executor:
            sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

            async def process_one(idx: int, product: Dict) -> None:
                product = normalize_product_defaults(product)
                url = product.get("url")
                if not url:
                    return

                async with sem:
                    product_name = product.get("product_name", "")
                    logger.info(f"[{idx}] Перевірка: {str(product_name)[:40]}...")

                    res = await get_product_data_async(session, executor, product)

                    now_iso = datetime.now().isoformat(timespec="seconds")
                    now_legacy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if res["error"]:
                        updates_by_url[url] = {
                            "last_checked_iso": now_iso,
                            "last_checked": now_legacy,
                            "availability_code": "ERROR",
                            "availability_text": "Помилка мережі/бан",
                        }
                        return

                    data = res["data"] or {}

                    if data.get("selector_error"):
                        updates_by_url[url] = {
                            "last_checked_iso": now_iso,
                            "last_checked": now_legacy,
                            "availability_code": "ERROR",
                            "availability_text": "Помилка селектора",
                        }
                        await notify_selector_error(
                            session,
                            product.get("product_name", "Невідомий товар"),
                            url,
                            data["selector_error"],
                        )
                        return

                    is_avail = data.get("is_available")
                    price = data.get("price")
                    scraped_img = data.get("image_url")
                    manual_img = product.get("manual_image_url")
                    image_current = manual_img or scraped_img

                    availability_code = "AVAILABLE" if is_avail else "OUT_OF_STOCK"
                    availability_text = data.get("availability_text") or (
                        "В наявності" if is_avail else "Немає в наявності"
                    )

                    updates_by_url[url] = {
                        "last_checked_iso": now_iso,
                        "last_checked": now_legacy,
                        "availability_code": availability_code,
                        "availability_text": availability_text,
                        "price_current": price,
                        "price_text": format_price_text(price),
                        "image_current": image_current,
                        "is_available_last": is_avail,
                        "price_last": price,
                    }

                    await asyncio.sleep(RATE_LIMIT_DELAY + random.uniform(0.0, 0.3))

            tasks = [process_one(i, p) for i, p in enumerate(products_snapshot, 1)]
            await asyncio.gather(*tasks)

    def mutator(products_from_disk: List[Dict]) -> List[Dict]:
        updated = _merge_updates_into_products(products_from_disk, updates_by_url)
        if len(updated) < len(products_from_disk):
            logger.error("❌ Захист: спроба видалити продукти. Повертаємо оригінал.")
            return products_from_disk
        return updated

    update_products_locked(mutator)

    await _send_notifications_after_update(products_snapshot, updates_by_url)
    logger.info("✅ Оновлення застосовано та збережено.")


async def _send_notifications_after_update(products_snapshot: List[Dict], updates_by_url: Dict[str, Dict]) -> None:
    old_by_url = {p.get("url"): p for p in products_snapshot if p.get("url")}

    # Вже оновлені дані з Supabase
    products_final = load_products()

    new_by_url = {p.get("url"): p for p in products_final if p.get("url")}

    if not updates_by_url:
        return

    async with aiohttp.ClientSession() as session:
        for url in updates_by_url.keys():
            p_old = old_by_url.get(url)
            p_new = new_by_url.get(url)

            if not p_old or not p_new:
                continue

            if (p_new.get("availability_code") or "").upper() == "ERROR":
                continue

            last_avail = p_old.get("is_available_last")
            last_price = p_old.get("price_last")
            new_avail = p_new.get("is_available_last")
            new_price = p_new.get("price_last")

            should_notify = False
            msg_parts = []

            if NOTIFY_ON_FIRST_CHECK and last_avail is None and new_avail:
                should_notify = True
                msg_parts.append("🆕 <b>НОВИЙ ТОВАР В БАЗІ!</b> 🟢")
                msg_parts.append("📊 Статус: В наявності")
                if new_price:
                    msg_parts.append(f"💰 Ціна: {new_price:.2f} грн")

            elif NOTIFY_ON_AVAILABILITY_CHANGE and last_avail is not None and last_avail != new_avail:
                should_notify = True
                if new_avail:
                    msg_parts.append("🎉 <b>НОВЕ НАДХОДЖЕННЯ!</b> 🟢")
                else:
                    msg_parts.append("⚠️ <b>ТОВАР ЗАКІНЧИВСЯ!</b> 🔴")

            if NOTIFY_ON_PRICE_CHANGE and new_price is not None and last_price is not None:
                diff = new_price - last_price
                if last_price > 0:
                    percent_change = abs(diff / last_price * 100)
                    if percent_change >= MIN_PRICE_CHANGE_PERCENT:
                        should_notify = True
                        icon = "👇" if diff < 0 else "⬆️"
                        msg_parts.append(
                            f"💰 <b>ЗМІНА ЦІНИ!</b> {icon}\n"
                            f"Стара: {last_price:.2f} грн → Нова: {new_price:.2f} грн\n"
                            f"Різниця: {diff:+.2f} грн ({percent_change:.1f}%)"
                        )

            if should_notify:
                # Determine event type
                is_price_change = NOTIFY_ON_PRICE_CHANGE and new_price is not None and last_price is not None and abs(new_price - last_price) / (last_price or 1) * 100 >= MIN_PRICE_CHANGE_PERCENT
                is_avail_change = NOTIFY_ON_AVAILABILITY_CHANGE and last_avail is not None and last_avail != new_avail
                is_new_product = NOTIFY_ON_FIRST_CHECK and last_avail is None and new_avail
                
                # Custom status icon (flag for Primaveo as in screenshot 1)
                status_icon = "🇮🇹" if "Primaveo" in (p_new.get("supplier") or "") else "📊"
                
                if is_price_change:
                    diff = new_price - last_price
                    percent_change = abs(diff / last_price * 100)
                    price_icon = "⬆️" if diff > 0 else "⬇️"
                    
                    full_message = (
                        f"💰 <b>ЗМІНА ЦІНИ!</b> {price_icon}\n\n"
                        f"📦 <b>{p_new.get('product_name')}</b>\n\n"
                        f"Стара: {last_price:.2f} грн → Нова: {new_price:.2f} грн\n\n"
                        f"Різниця: {diff:+.2f} грн ({percent_change:.1f}%)\n\n"
                        f"🏪 Постачальник: {p_new.get('supplier', '—')}\n\n"
                        f"🎨 Колір: {p_new.get('color', '—')}\n\n"
                        f"🔗 <a href='{url}'>Посилання на товар</a>"
                    )
                elif is_avail_change:
                    header = "🎉 <b>ЗНОВУ В НАЯВНОСТІ</b> 🟢" if new_avail else "⚠️ <b>ТОВАР ЗАКІНЧИВСЯ!</b> 🔴"
                    full_message = (
                        f"{header}\n\n"
                        f"📦 <b>{p_new.get('product_name')}</b>\n\n"
                        f"🎨 Колір: {p_new.get('color', '—')}\n\n"
                        f"🏪 Постачальник: {p_new.get('supplier', '—')}\n\n"
                        f"🔗 <a href='{url}'>Посилання на товар</a>"
                    )
                elif is_new_product:
                    full_message = (
                        f"🆕 <b>НОВИЙ ТОВАР В БАЗІ!</b> 🟢\n\n"
                        f"📦 <b>{p_new.get('product_name')}</b>\n\n"
                        f"{status_icon} Статус: {p_new.get('availability_text', '—')}\n\n"
                        f"🎨 Колір: {p_new.get('color', '—')}\n\n"
                        f"💰 Ціна: {new_price:.2f} грн\n\n"
                        f"🏪 Постачальник: {p_new.get('supplier', '—')}\n\n"
                        f"🔗 <a href='{url}'>Посилання на товар</a>"
                    )
                else:
                    # Generic fallback just in case
                    full_message = "\n".join(msg_parts) + f"\n\n📦 <b>{p_new.get('product_name')}</b>\n🔗 <a href='{url}'>Link</a>"
                
                logger.info(f"📨 Відправка сповіщення для: {p_new.get('product_name')}")
                await send_telegram_async(session, full_message, photo_url=p_new.get('image_current'))


def run_checker() -> None:
    CHECK_INTERVAL = 15 * 60

    print("\n" + "=" * 60)
    print("🚀 PRICE CHECKER STARTED (FIXED VERSION)")
    print("🔒 Unified File-lock: file_lock.py")
    print("📦 Unified Data: product_data.py")
    print("=" * 60)
    print(f"📢 Сповіщення при першій перевірці: {'✅' if NOTIFY_ON_FIRST_CHECK else '❌'}")
    print(f"📢 Сповіщення при зміні наявності: {'✅' if NOTIFY_ON_AVAILABILITY_CHANGE else '❌'}")
    print(f"📢 Сповіщення при зміні ціни: {'✅' if NOTIFY_ON_PRICE_CHANGE else '❌'} (>{MIN_PRICE_CHANGE_PERCENT}%)")
    print("=" * 60 + "\n")

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN або TELEGRAM_CHAT_ID не задані — сповіщення вимкнені!")

    while True:
        try:
            start = time.time()
            asyncio.run(check_products())
            elapsed = time.time() - start

            logger.info(f"🏁 Цикл завершено за {elapsed:.2f} сек.")
            logger.info(f"💤 Сон {CHECK_INTERVAL} сек...")
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n🛑 Зупинено користувачем.")
            break

        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR: {e}", exc_info=True)
            time.sleep(60)


if __name__ == "__main__":
    run_checker()
