"""Секреты и личные идентификаторы — только из .env проекта (<корень>/.env, права 600, вне git), 27.10.2026.
Не из config.json (он уходит заказчику как config.example.json) и не из файлов других проектов.
Переменные: POLZA_API_KEY (ключ API модели), MAX_BOT_TOKEN (бот MAX), TG_ADMIN_ID, TG_BOT_USERNAME (администратор и бот Telegram),
SETTINGS_USERS, MAX_ALLOWED_USERS (id через запятую). Нет файла или строки — пустое значение, не исключение: боты ждут токен.
Тесты подменяют файл переменной окружения CS_ENV_FILE."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.environ.get("CS_ENV_FILE") or f"{ROOT}/.env"

def read(name, default=""):
    try:
        for l in open(PATH, encoding="utf-8"):
            if l.startswith(name + "="): return l.split("=", 1)[1].strip().strip('"') or default
    except OSError: pass
    return default

def int_(name, default=0):
    v = read(name)
    return int(v) if v.strip().lstrip("-").isdigit() else default

def ints(name):
    return {int(x) for x in read(name).replace(";", ",").split(",") if x.strip().lstrip("-").isdigit()}

def config():
    """config.json проекта; у заказчика до копирования — config.example.json (те же ключи, без личных данных)."""
    for f in ("config.json", "config.example.json"):
        p = f"{ROOT}/{f}"
        if os.path.exists(p): return json.load(open(p, encoding="utf-8"))
    raise FileNotFoundError(f"{ROOT}/config.json: скопируйте config.example.json → config.json")
