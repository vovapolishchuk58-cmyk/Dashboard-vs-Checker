# file_lock.py - Спільний модуль для міжпроцесного блокування
# Використовується як checker.py, так і dashboardgimini.py

import os
import time
import re
from contextlib import contextmanager
from datetime import datetime

LOCK_TIMEOUT_SECONDS = 20
LOCK_POLL_INTERVAL_SECONDS = 0.1

# ✅ NEW: self-heal settings
STALE_LOCK_SECONDS = 120  # lock старше цього часу вважаємо потенційно "битим"


def _parse_lock_file(lock_file: str):
    """
    Очікуваний формат:
      pid=123 ts=2026-02-03T12:34:56.123456
    """
    try:
        with open(lock_file, "r", encoding="utf-8") as f:
            s = f.read()
        pid_m = re.search(r"pid=(\d+)", s)
        ts_m = re.search(r"ts=([0-9T:\.\-]+)", s)
        pid = int(pid_m.group(1)) if pid_m else None
        ts = ts_m.group(1) if ts_m else None
        return pid, ts
    except Exception:
        return None, None


def _pid_is_running(pid: int) -> bool:
    """
    Unix: os.kill(pid, 0) перевіряє існування процесу.
    Windows: працює не завжди, але безпечно фейлиться в except.
    """
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _is_lock_stale(lock_file: str) -> bool:
    try:
        age = time.time() - os.path.getmtime(lock_file)
        return age > STALE_LOCK_SECONDS
    except Exception:
        return False


def _try_break_stale_lock(lock_file: str) -> bool:
    """
    Повертає True, якщо вдалося видалити протухлий lock.
    Логіка:
      - якщо lock старий (mtime > STALE_LOCK_SECONDS)
      - і PID не живий (або pid не прочитався)
      -> видаляємо lock
    """
    if not os.path.exists(lock_file):
        return False

    pid, _ = _parse_lock_file(lock_file)

    if _is_lock_stale(lock_file) and (not pid or not _pid_is_running(pid)):
        try:
            os.remove(lock_file)
            print(f"🧹 Removed stale lock: {lock_file} (pid={pid})")
            return True
        except Exception:
            return False

    return False


@contextmanager
def acquire_file_lock(lock_file: str, timeout_seconds: int = LOCK_TIMEOUT_SECONDS):
    """
    Міжпроцесний lock через атомарне створення lock-файлу.
    Працює без сторонніх бібліотек.

    ✅ Покращення:
      - self-heal: видалення протухлого lock (після падіння процесу)

    Args:
        lock_file: Шлях до lock-файлу
        timeout_seconds: Максимальний час очікування lock

    Raises:
        TimeoutError: Якщо не вдалося отримати lock за вказаний час
    """
    start = time.time()
    lock_acquired = False

    while not lock_acquired:
        try:
            # O_EXCL гарантує, що файл створиться лише якщо його не існує
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"pid={os.getpid()} ts={datetime.now().isoformat()}\n")
                f.flush()  # ✅ Force write to disk (Windows fix)
                os.fsync(f.fileno())  # ✅ Ensure data is written
            lock_acquired = True
        except FileExistsError:
            # ✅ NEW: self-heal stale lock
            _try_break_stale_lock(lock_file)

            if time.time() - start > timeout_seconds:
                raise TimeoutError(
                    f"Не вдалося отримати lock за {timeout_seconds}s: {lock_file}"
                )
            time.sleep(LOCK_POLL_INTERVAL_SECONDS)

    try:
        yield
    finally:
        # ✅ FIX Windows: Multiple attempts to remove lock file
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                break  # Success
            except FileNotFoundError:
                break  # Already removed
            except PermissionError:
                # Windows може ще тримати файл відкритим
                if attempt < max_attempts - 1:
                    time.sleep(0.05)  # 50ms delay
                else:
                    print(f"⚠️ Не вдалося видалити lock-файл {lock_file} після {max_attempts} спроб (PermissionError)")
            except Exception as e:
                if attempt < max_attempts - 1:
                    time.sleep(0.05)
                else:
                    print(f"⚠️ Не вдалося видалити lock-файл {lock_file}: {e}")
