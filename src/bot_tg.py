"""Бот Telegram «Капитан Сэм» (показ 12.10.2026): тот же обработчик, что у бота MAX (bot_max.handle): текст → docx.
- Токен: /root/secrets/captain-sam-bot.env, строка TG_BOT_TOKEN=… Нет файла → не падает, проверяет раз в 60 с.
- Доступ: неизвестный пишет боту → Вадиму через @vadim_sbrain_bot запрос «пустить <имя, @username>?» с кнопками-ссылками
  «Да»/«Нет» на этого бота (t.me/<бот>?start=ok_<код> / no_<код>). Кнопки — ссылки, а не callback: @vadim_sbrain_bot опрашивает
  другой процесс, его callback сюда не дойдёт. Решение принимается, только если /start ok_… прислал сам Вадим (TG_ADMIN_ID из .env).
- Список допущенных и ожидающих — build/mvp/tg_access.json (не в git). В лог — счётчики, без текста претензий.

  python3 src/bot_tg.py
"""
import json, os, secrets, sys, time, uuid, urllib.request, urllib.parse, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import env_file as EF   # 27.10: id администратора — из .env проекта
CFG = EF.config()
API = os.environ.get("CS_TG_API") or "https://api.telegram.org"     # env — только для теста на поддельном API
ENV = os.environ.get("CS_TG_ENV") or "/root/secrets/captain-sam-bot.env"
NOTIFY_TOKEN_FILE = os.environ.get("CS_TG_NOTIFY") or "/etc/tg-tokens/vadim_sbrain"   # @vadim_sbrain_bot — только отправка
ADMIN = EF.int_("TG_ADMIN_ID")
ACCESS = os.environ.get("CS_TG_ACCESS") or f"{ROOT}/build/mvp/tg_access.json"
OFFSET = os.environ.get("CS_TG_OFFSET") or f"{ROOT}/build/mvp/tg_offset"
START = "Присылайте претензию без ФИО, телефонов и адресов покупателя."

def log(*a): print(time.strftime("%F %T"), *a, flush=True)

def token():
    try:
        for l in open(ENV, encoding="utf-8"):
            if l.startswith("TG_BOT_TOKEN="): return l.split("=", 1)[1].strip().strip('"') or None
    except OSError: pass
    return None

def api(tok, method, params=None, files=None, timeout=60):
    url = f"{API}/bot{tok}/{method}"
    if files:
        b = uuid.uuid4().hex; parts = []
        for k, v in (params or {}).items():
            parts.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
        for k, path in files.items():
            parts.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{os.path.basename(path)}\"\r\n"
                         f"Content-Type: application/octet-stream\r\n\r\n".encode() + open(path, "rb").read() + b"\r\n")
        data = b"".join(parts) + f"--{b}--\r\n".encode(); h = {"Content-Type": f"multipart/form-data; boundary={b}"}
    else:
        data = json.dumps(params or {}).encode(); h = {"Content-Type": "application/json"}
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=timeout) as r:
        return json.load(r).get("result")

def load():
    try: return json.load(open(ACCESS, encoding="utf-8"))
    except (OSError, ValueError): return {"allowed": {}, "pending": {}}

def save(acc):
    tmp = ACCESS + ".tmp"; json.dump(acc, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o640); os.replace(tmp, ACCESS)

def who(u): return " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x) + (f", @{u['username']}" if u.get("username") else "")

def ask_admin(bot_name, u, acc):
    for code, p in acc["pending"].items():
        if p["user_id"] == u["id"]: return False          # запрос уже отправлен
    code = secrets.token_hex(4)
    acc["pending"][code] = {"user_id": u["id"], "who": who(u), "ts": int(time.time())}; save(acc)
    ntok = open(NOTIFY_TOKEN_FILE).read().strip()
    api(ntok, "sendMessage", {"chat_id": ADMIN, "text": f"Бот «Капитан Сэм»: пустить {who(u)}?",
        "reply_markup": {"inline_keyboard": [[{"text": "Да", "url": f"https://t.me/{bot_name}?start=ok_{code}"},
                                              {"text": "Нет", "url": f"https://t.me/{bot_name}?start=no_{code}"}]]}})
    return True

def poll_once(tok, bot_name, offset):
    import bot_max as BM   # общий обработчик: текст → docx (handle), без сети MAX
    ups = api(tok, "getUpdates", {"timeout": 15, "offset": offset, "allowed_updates": ["message"]}, timeout=30) or []   # 15 с — чтобы ожидание КП (2 мин) не затягивалось
    for up in ups:
        offset = up["update_id"] + 1
        m = up.get("message") or {}; u = m.get("from") or {}; chat = (m.get("chat") or {}).get("id"); text = (m.get("text") or "").strip()
        if not u or chat is None or (m.get("chat") or {}).get("type") != "private": continue
        acc = load(); uid = u["id"]
        # решение Вадима по ссылке из запроса
        if text.startswith("/start mok_") or text.startswith("/start mno_"):   # решение о доступе в бот MAX (запрос пришёл из bot_max.py)
            if uid != ADMIN: api(tok, "sendMessage", {"chat_id": chat, "text": "Решение о доступе принимает администратор."}); continue
            macc = BM.load_access(); p = macc["pending"].pop(text.split("_", 1)[1], None)
            if not p: BM.save_access(macc); api(tok, "sendMessage", {"chat_id": chat, "text": "Запрос MAX не найден или уже решён."}); continue
            ok = text.startswith("/start mok_")
            if ok: macc["allowed"][str(p["user_id"])] = {"who": p["who"], "since": time.strftime("%F %T")}
            BM.save_access(macc)
            mt = BM.token()
            if mt: BM.send_text(mt, p["user_id"], ("Доступ открыт. " + BM.START) if ok else "Доступ не предоставлен.")
            api(tok, "sendMessage", {"chat_id": chat, "text": f"MAX: {'доступ открыт' if ok else 'отказано'} — {p['who']}"})
            log("MAX доступ", "открыт" if ok else "отказ", p["user_id"]); continue
        if text.startswith("/start ok_") or text.startswith("/start no_"):
            code = text.split("_", 1)[1]
            if uid != ADMIN: api(tok, "sendMessage", {"chat_id": chat, "text": "Решение о доступе принимает администратор."}); continue
            p = acc["pending"].pop(code, None)
            if not p: api(tok, "sendMessage", {"chat_id": chat, "text": "Запрос не найден или уже решён."}); save(acc); continue
            if text.startswith("/start ok_"):
                acc["allowed"][str(p["user_id"])] = {"who": p["who"], "since": time.strftime("%F %T")}; save(acc)
                api(tok, "sendMessage", {"chat_id": p["user_id"], "text": "Доступ открыт. " + START})
                api(tok, "sendMessage", {"chat_id": chat, "text": f"Доступ открыт: {p['who']}"}); log("доступ открыт", p["user_id"])
            else:
                save(acc); api(tok, "sendMessage", {"chat_id": p["user_id"], "text": "Доступ не предоставлен."})
                api(tok, "sendMessage", {"chat_id": chat, "text": f"Отказано: {p['who']}"}); log("отказ в доступе", p["user_id"])
            continue
        if uid != ADMIN and str(uid) not in acc["allowed"]:
            sent = ask_admin(bot_name, u, acc)
            api(tok, "sendMessage", {"chat_id": chat, "text": "Запрос на доступ отправлен администратору." if sent else "Запрос на доступ уже отправлен, ждите."})
            log("запрос доступа", uid); continue
        doc = m.get("document")
        if doc:   # 09.10: КП объекта (PDF) — подписью может идти текст претензии
            if not (doc.get("mime_type") == "application/pdf" or str(doc.get("file_name", "")).lower().endswith(".pdf")):
                api(tok, "sendMessage", {"chat_id": chat, "text": "Пришлите КП объекта в PDF."}); continue
            kp = download(tok, doc["file_id"]); cap = (m.get("caption") or "").strip(); pend = PENDING.get(chat)
            if cap: process(tok, chat, uid, cap, kp); PENDING.pop(chat, None)
            elif pend and pend.get("text") and time.time() - pend["ts"] <= WAIT: PENDING.pop(chat); process(tok, chat, uid, pend["text"], kp)
            else:
                PENDING[chat] = {"kp": kp, "ts": time.time(), "uid": uid}
                api(tok, "sendMessage", {"chat_id": chat, "text": "КП получено. Пришлите текст претензии (в течение 2 минут)."})
            continue
        if text in ("", "/start", "/help") or text.startswith("/start"):
            api(tok, "sendMessage", {"chat_id": chat, "text": START + "\n\n" + BM.HELP}); continue
        pend = PENDING.get(chat)
        if pend and pend.get("kp") and time.time() - pend["ts"] <= WAIT:
            PENDING.pop(chat); process(tok, chat, uid, text, pend["kp"]); continue
        PENDING[chat] = {"text": text, "ts": time.time(), "uid": uid}
        log("запрос от", uid, "символов", len(text), "— ждём КП")
        api(tok, "sendMessage", {"chat_id": chat, "text": "Принято. Если есть КП объекта (PDF) — пришлите его в течение 2 минут, "
                                                         "ответ будет по проекту покупателя. Иначе отвечу без него."})
    flush(tok)
    if ups: open(OFFSET, "w").write(str(offset))
    return offset

WAIT = 120   # сек.: КП следом за претензией (или претензия следом за КП)
PENDING = {}   # chat → {"text"| "kp", "ts", "uid"}
KP_DIR = os.environ.get("CS_TG_KP") or f"{ROOT}/build/mvp/bot/kp"

def download(tok, file_id):
    """Файл из Telegram → build/mvp/bot/kp/ (600). Данные заказчика — только на Питере."""
    f = api(tok, "getFile", {"file_id": file_id})
    os.makedirs(KP_DIR, exist_ok=True); path = f"{KP_DIR}/kp_{time.strftime('%Y%m%d_%H%M%S')}.pdf"
    with urllib.request.urlopen(f"{API}/file/bot{tok}/{f['file_path']}", timeout=60) as r: open(path, "wb").write(r.read())
    os.chmod(path, 0o600); return path

def process(tok, chat, uid, text, kp=None):
    import bot_max as BM
    log("ответ готовится", uid, "символов", len(text), "КП:", "да" if kp else "нет")
    try:
        api(tok, "sendMessage", {"chat_id": chat, "text": "Принято, готовлю ответ — обычно до минуты на пункт."})
        paths, summary, outs = BM.handle(text, [kp] if kp else None)   # 15.10: handle принимает список файлов проекта
        api(tok, "sendMessage", {"chat_id": chat, "text": summary})
        for p in paths: api(tok, "sendDocument", {"chat_id": chat}, files={"document": p}, timeout=120)
        log("ответ", uid, "файлов", len(paths), "пунктов", len(outs))
    except Exception as e:
        log("ошибка", type(e).__name__); api(tok, "sendMessage", {"chat_id": chat, "text": "Не получилось подготовить ответ. Попробуйте позже."})

def flush(tok):
    """Претензии, к которым за 2 минуты не пришёл КП, — ответ без КП (с подсказкой в сводке)."""
    for chat, p in list(PENDING.items()):
        if time.time() - p["ts"] > WAIT:
            PENDING.pop(chat)
            if p.get("text"): process(tok, chat, p["uid"], p["text"], None)

def main():
    offset = int(open(OFFSET).read()) if os.path.exists(OFFSET) else None
    bot_name = None
    while True:
        tok = token()
        if not tok: time.sleep(60); continue
        try:
            bot_name = bot_name or api(tok, "getMe")["username"]
            offset = poll_once(tok, bot_name, offset)
        except Exception as e:
            log("updates:", type(e).__name__, getattr(e, "code", "")); time.sleep(10)

if __name__ == "__main__":
    main()
