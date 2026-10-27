"""Бот MAX «Капитан Сэм»: текст претензии (или несколько пунктов списком) → docx с ответом покупателю. Сервер — Питер.
- Токен: ОДНА строка MAX_BOT_TOKEN=… в /opt/captain-sam/.env (600, вне git). Переход на бота заказчика = замена этой строки.
- Доступ: только user_id из .env → MAX_ALLOWED_USERS. Чужим — «доступ закрыт», текст не обрабатывается и не пишется в лог.
- Обезличивание — внутри answer() до вызова модели. В лог — только счётчики, без текста претензий.
- Нет токена → не падает, проверяет .env раз в 60 с.

  python3 src/bot_max.py                         # боевой режим (long polling)
  python3 src/bot_max.py --emulate файл.txt      # локальный эмулятор: текст из файла → docx, без MAX
"""
import json, os, re, sys, time, uuid, urllib.request, urllib.error, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import env_file as EF   # 27.10: токен, id администратора и списки пользователей — из .env проекта
CFG = EF.config()
API = os.environ.get("CS_MAX_API") or CFG.get("max_api", "https://platform-api2.max.ru")   # env — только для теста на поддельном API
ALLOWED = EF.ints("MAX_ALLOWED_USERS")   # статический список (если задан) + допущенные по запросу (max_access.json)
ACCESS = os.environ.get("CS_MAX_ACCESS") or f"{ROOT}/build/mvp/max_access.json"
NOTIFY_TOKEN_FILE = os.environ.get("CS_TG_NOTIFY") or "/etc/tg-tokens/vadim_sbrain"   # @vadim_sbrain_bot — только отправка
TG_API = os.environ.get("CS_TG_API") or "https://api.telegram.org"
TG_ADMIN = EF.int_("TG_ADMIN_ID")
TG_BOT = EF.read("TG_BOT_USERNAME")   # решения по доступу в MAX Вадим нажимает в Telegram — там он получает запрос
START = "Присылайте претензию без ФИО, телефонов и адресов покупателя."
KP_HOLD = 1800   # сек.: файлы проекта без текста претензии — хранение 30 мин; то же окно — повторный разбор,
                 # если КП пришёл после ответа без него (12.10.2026)
ANSWERED = {}    # user_id → {"text", "ts"}: последняя претензия, отвеченная БЕЗ данных проекта, — для повтора с ними
REDO = {}        # user_id → {"text", "docs", "ts"}: ждём досылки файлов DOC_WAIT сек., потом один повторный разбор
MAX_DOCS = 5     # файлов проекта к одной претензии
DOC_WAIT = 60    # сек.: окно досылки файлов перед повторным разбором — иначе каждый файл стоил бы отдельного разбора
PENDING = {}
WHO = {}          # user_id → «Имя, @username» для уведомлений Вадиму
KP_DIR = os.environ.get("CS_MAX_KP") or f"{ROOT}/build/mvp/bot/kp"   # 15.10: любые файлы данных проекта, не только КП
MAX_CLAIMS = int(CFG.get("max_claims_per_message", 10))   # потолок расходов: ~2 ₽ на пункт
OUT = f"{ROOT}/build/mvp/bot"; STATE = f"{ROOT}/build/mvp/bot_marker"
DOC_EXT = (".pdf", ".docx", ".odt")   # 20.10: претензия может прийти файлом; данные проекта — PDF
ASKS = {}        # 20.10: ключ → {"uid", "path", "name", "ts"}: нераспознанный файл ждёт кнопки «претензия / данные проекта»
NOTIFY_Q = []    # 20.10: неотправленные уведомления — 3 попытки с паузой NOTIFY_PAUSE, потом в NOTIFY_FAILED
NOTIFY_PAUSE = 60
NOTIFY_FAILED = os.environ.get("CS_NOTIFY_FAILED") or f"{ROOT}/build/mvp/notify_failed.jsonl"
CLAIM_BTN_HINT = "Если это претензия — нажмите кнопку «Это претензия» или пришлите её текстом."
SHORT_MAX = 15   # 20.10: сообщение короче — без строительных слов это не замечание («1», «ок», «привет»)
CONSTR = re.compile(r"(?i)двер|окн|окон|стеклопакет|кровл|крыш|стен|фасад|сайдинг|фундамент|сва[яий]|ростверк|обвязк|перекрыт|"
                    r"пол\b|потол|стропил|брус|лаг|утепл|мембран|OSB|ОСБ|котл|котёл|отоплен|вентил|электр|автомат|УЗО|фаз|кВт|"
                    r"конденс|влаж|протеч|теч[её]т|мост|трещин|гни|плесен|сейсм|снег|ветр|шум")
SHORT_HINT = ("Пришлите замечание покупателя: текстом — одним сообщением (несколько пунктов — списком) или файлом "
              "(PDF, DOCX, ODT). Например: «Кровля из ондулина протечёт на стыках листов».")
HELP = ("Пришлите текст претензии покупателя — одним сообщением. Несколько пунктов — списком (1. … 2. …).\n"
        f"В ответ придёт документ с ответом по каждому пункту (до {MAX_CLAIMS} пунктов за раз). "
        "Пункты без подтверждённого основания помечаются «передано инженеру».")

def log(*a): print(time.strftime("%F %T"), *a, flush=True)

def token():
    return EF.read("MAX_BOT_TOKEN") or None

def call(method, path, tok, body=None, params=None, raw=None, headers=None):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    h = {"Authorization": tok}; h.update(headers or {})
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if body is not None: h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=90) as r: return json.load(r)

def send_text(tok, uid, text): call("POST", "/messages", tok, {"text": text}, {"user_id": uid})

def send_file(tok, uid, path, text):
    up = call("POST", "/uploads", tok, params={"type": "file"})
    b = uuid.uuid4().hex; name = os.path.basename(path)
    payload = (f"--{b}\r\nContent-Disposition: form-data; name=\"data\"; filename=\"{name}\"\r\n"
               f"Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n").encode() \
              + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(up["url"], data=payload, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}", "Authorization": tok})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = r.read()
    try: ftok = json.loads(resp).get("token") or up.get("token")
    except ValueError: ftok = up.get("token")
    for attempt in range(6):   # файл обрабатывается не сразу: attachment.not.ready → пауза и повтор
        try:
            body = {"attachments": [{"type": "file", "payload": {"token": ftok}}]}
            if text: body["text"] = text
            return call("POST", "/messages", tok, body,
                        {"user_id": uid})
        except urllib.error.HTTPError as e:
            if "not.ready" in e.read().decode("utf-8", "replace") and attempt < 5: time.sleep(2 + attempt * 2); continue
            raise

KP_HINT = ("Если есть данные проекта — пришлите PDF: КП, опросный лист или теплотехнический расчёт "
            "(можно несколько файлов). Переделаю ответ по проекту.")

def project_object(paths):
    """Файлы проекта (PDF) → (данные проекта для генератора, перечень разобранного). 15.10: КП, опросный лист,
    теплотехнический расчёт — разбор src/project_docs.py (обезличенно). (None, …) — позиций не дал ни один файл."""
    if not paths: return None, []
    try:
        import project_docs as PD
        return PD.build_docs(paths)
    except Exception as e:
        log("данные проекта не разобраны:", type(e).__name__); return None, []

def doc_names(paths):
    """Перечисление присланных файлов для сообщения: «опросный лист от 09.10.2026, теплотехнический расчёт от 15.10.2026»."""
    import project_docs as PD
    out = []
    for f in paths:
        try:
            k = PD.kind(f); d = PD.date_of(f)
            out.append(f"{k} от {d}" if k and d else (k or "файл неизвестного вида"))
        except Exception as e:
            log("вид файла не определён:", type(e).__name__); out.append("файл неизвестного вида")
    return ", ".join(out)

def handle(text, docs=None, redo=False, claims=None, first=1, part=None):
    """Текст → ([пути к docx], сводка для менеджера, outs). Без сети. Продукт — проект ответа + проверка человеком (08.10):
    «Ответ покупателю» — только пункты, прошедшие все проверки; «Черновик для инженера» (внутренний) — остальные."""
    import answer as A, answer_docx as D
    claims = claims or A.split_claims(text)[:MAX_CLAIMS]   # 20.10: претензия файлом — готовые пункты по разделам
    obj, read = project_object(docs or [])
    outs = [A.answer(c, obj)[0] for c in claims]
    os.makedirs(OUT, exist_ok=True); ts = time.strftime('%Y%m%d_%H%M%S') + (f"_p{first}" if part else ""); paths = []
    client = [(n, o) for n, o in enumerate(outs, first) if o["route"] == "client"]   # 20.10: нумерация сквозная по частям
    eng = [(n, o) for n, o in enumerate(outs, first) if o["route"] == "engineer"]
    mark = None
    if redo and obj: mark = f"Ответ по проекту ({obj['sources']})"
    if client:
        p = f"{OUT}/otvet_pokupatelyu_{ts}.docx"
        D.render([o for _, o in client], p, numbers=[n for n, _ in client], mark=mark); paths.append(p)
    if eng:
        p = f"{OUT}/chernovik_inzheneru_{ts}.docx"; D.render_engineer(eng, p); paths.append(p)
    for p in paths: os.chmod(p, 0o640)
    # служебный разбор: вердикт, причина «инженеру», проверка текста — обезличенно, без исходных имён
    js = f"{OUT}/razbor_{ts}.json"
    json.dump([{k: v for k, v in o.items() if k != "mapping"} for o in outs], open(js, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.chmod(js, 0o640)
    where = "" if not eng else (" (черновик во втором файле)" if client else " (черновик в файле)")
    summary = (f"Часть {part[0]} из {part[1]} (пп. {first}–{first + len(outs) - 1}). " if part else "") + \
              f"Пунктов {len(outs)}. Готово для покупателя — {len(client)}. На проверку инженеру — {len(eng)}{where}."
    summary += "\n" + verdict_summary(outs)   # 21.10: разбивка по типам вердикта (Прил. 1, п. 2.5)
    need = [(n, o) for n, o in enumerate(outs, first) if (o.get("internal") or {}).get("need_project")]
    if need:   # 12.10: о данных проекта спрашиваем сотрудника, не покупателя
        # 16.10: каждый пункт отдельной строкой — склейка перечней через «;» не показывала, какой перечень к какому пункту
        summary += "\nОтвет зависит от данных проекта:" + "".join(
            f"\nп. {n} — нужны {o['internal']['need_project']}" for n, o in need)
        if not obj: summary += "\nПришлите данные проекта — переделаю ответ."
    me = [n for n, o in enumerate(outs, first) if (o.get("internal") or {}).get("model_error")]
    if me:   # 17.10: П-5 — явная строка, чего нет
        summary += (f"\n⚠ Модель недоступна: по п. {', '.join(map(str, me))} разбора нет — в черновике нормы из поиска"
                    " и расчёт, ответ нужно написать вручную или прислать пункт ещё раз.")
    es = [n for n, o in enumerate(outs, first) if (o.get("internal") or {}).get("empty_search")]
    if es:   # 17.10: П-8 — пустой поиск — явная причина
        summary += (f"\n⚠ По п. {', '.join(map(str, es))} поиск не нашёл ни одной нормы — разбор не делали."
                    " Пришлите суть замечания текстом.")
    bad = [d for d in read if not d["items"]]
    if bad: summary += "\n" + "\n".join(f"{d['kind'] or 'файл'} ({d['file']}): {d['note']}" for d in bad) + \
                       ("\n" + CLAIM_BTN_HINT if any(not d["kind"] for d in bad) else "")   # 20.10: нераспознанный файл
    if not obj and not part: summary += "\n" + (KP_HINT if not docs else "Данные проекта не разобраны — ответ без них. " + KP_HINT)
    else:
        summary += f"\nДанные проекта: {obj['sources']}."
        if mark: summary = f"Переделал ответ по проекту ({obj['sources']}).\n" + summary
    if text and len(A.split_claims(text)) > MAX_CLAIMS: summary += f"\nОбработаны первые {MAX_CLAIMS} пунктов — остальные пришлите отдельно."
    return paths, summary, outs

def main():
    if "--emulate" in sys.argv:
        text = open(sys.argv[sys.argv.index("--emulate") + 1], encoding="utf-8").read()
        docs = sys.argv[sys.argv.index("--docs") + 1:] if "--docs" in sys.argv else (
               [sys.argv[sys.argv.index("--kp") + 1]] if "--kp" in sys.argv else None)
        paths, summary, outs = handle(text, docs)
        print(summary); [print("docx:", p) for p in paths]
        return
    marker = open(STATE).read().strip() if os.path.exists(STATE) else None
    while True:
        tok = token()
        if not tok: time.sleep(60); continue
        try: marker = poll_once(tok, marker)
        except Exception as e: log("updates:", type(e).__name__, getattr(e, "code", "")); time.sleep(10)

def load_access():
    try: return json.load(open(ACCESS, encoding="utf-8"))
    except (OSError, ValueError): return {"allowed": {}, "pending": {}}

def save_access(acc):
    tmp = ACCESS + ".tmp"; json.dump(acc, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o640); os.replace(tmp, ACCESS)

def allowed(uid): return uid in ALLOWED or str(uid) in load_access()["allowed"]

def who_str(user):
    who = user.get("name") or " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x) or "без имени"
    if user.get("username"): who += f", @{user['username']}"
    return who

def tg_send(body):
    req = urllib.request.Request(f"{TG_API}/bot{open(NOTIFY_TOKEN_FILE).read().strip()}/sendMessage", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()

def notify(text):
    """Вадиму в @vadim_sbrain_bot. Своей осечкой доставку покупателю не ронять — только строка в журнал.
    20.10: осечка → очередь, ещё 2 попытки с паузой NOTIFY_PAUSE (flush), потом — в NOTIFY_FAILED и в вечернюю строку."""
    try: tg_send({"chat_id": TG_ADMIN, "text": "Капитан Сэм / MAX\n" + text})
    except Exception as e:
        log("уведомление не ушло:", type(e).__name__, "(попытка 1/3, повтор)")
        NOTIFY_Q.append({"text": text, "tries": 1, "next": time.time() + NOTIFY_PAUSE, "first": time.strftime("%F %T", time.gmtime())})

def notify_retry():
    for q in list(NOTIFY_Q):
        if time.time() < q["next"]: continue
        try:
            tg_send({"chat_id": TG_ADMIN, "text": "Капитан Сэм / MAX (с задержкой)\n" + q["text"]}); NOTIFY_Q.remove(q)
            log("уведомление ушло с попытки", q["tries"] + 1)
        except Exception as e:
            q["tries"] += 1; q["next"] = time.time() + NOTIFY_PAUSE
            if q["tries"] >= 3:
                NOTIFY_Q.remove(q); log("уведомление не отправлено после 3 попыток:", type(e).__name__)
                try:
                    with open(NOTIFY_FAILED, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"ts": time.strftime("%F %T", time.gmtime()), "first": q["first"], "err": type(e).__name__,
                                            "head": q["text"].split("\n", 1)[0][:120]}, ensure_ascii=False) + "\n")
                except OSError as e2: log("журнал неотправленных не записан:", type(e2).__name__)

def routed(outs, key):
    return sum(1 for o in outs if isinstance(o, dict) and o.get("route") == key)

def ask_admin(user):
    """Новый пользователь MAX → Вадиму в @vadim_sbrain_bot «пустить …?» с кнопками-ссылками на Telegram-бота (mok_/mno_)."""
    import secrets
    acc = load_access()
    if any(p["user_id"] == user["user_id"] for p in acc["pending"].values()): return False
    code = secrets.token_hex(4); who = who_str(user)
    acc["pending"][code] = {"user_id": user["user_id"], "who": who, "ts": int(time.time())}; save_access(acc)
    tg_send({"chat_id": TG_ADMIN, "text": f"Бот «Капитан Сэм» в MAX: пустить {who}?",
             "reply_markup": {"inline_keyboard": [[{"text": "Да", "url": f"https://t.me/{TG_BOT}?start=mok_{code}"},
                                                   {"text": "Нет", "url": f"https://t.me/{TG_BOT}?start=mno_{code}"}]]}})
    return True

def download_file(tok, url, name="x.pdf"):
    """Вложение MAX → build/mvp/bot/kp/ (600): сначала без авторизации (подписанная ссылка), на 401/403 — с токеном.
    20.10: расширение — как у присланного файла (PDF, DOCX, ODT)."""
    ext = os.path.splitext(str(name).lower())[1] if str(name).lower().endswith(DOC_EXT) else ".pdf"
    os.makedirs(KP_DIR, exist_ok=True); path = f"{KP_DIR}/kp_max_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}{ext}"
    try: data = urllib.request.urlopen(url, timeout=60).read()
    except urllib.error.HTTPError as e:
        if e.code not in (401, 403): raise
        data = urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": tok}), timeout=60).read()
    open(path, "wb").write(data); os.chmod(path, 0o600); return path

def process(tok, uid, text, docs=None, redo=False):
    log("ответ готовится", uid, "символов", len(text), "файлов проекта:", len(docs or []), "повтор" if redo else "")
    t0 = time.time(); who = WHO.get(uid) or "без имени"; head = "🔁 Повтор с данными проекта\n" if redo else ""
    try:
        send_text(tok, uid, "Переделываю ответ по данным проекта." if redo
                  else "Принято, готовлю ответ — обычно до минуты на пункт.")
        if docs and scan_pending(docs): send_text(tok, uid, OCR_NOTE)   # 21.10: распознавание идёт в цикле бота — предупредить
        paths, summary, outs = handle(text, docs, redo)
        waiting = [a["name"] for a in ASKS.values() if a["uid"] == uid]
        if waiting: summary += f"\nФайл «{waiting[0]}» ждёт ответа на кнопки. " + CLAIM_BTN_HINT   # 20.10
        send_text(tok, uid, summary)
        for p in paths: send_file(tok, uid, p, "")
        log("ответ", uid, "файлов", len(paths), "пунктов", len(outs))
        if not docs and not redo: ANSWERED[uid] = {"text": text, "ts": time.time()}   # 30 мин на повтор с данными проекта
        me = [(n, o["internal"]["model_error"]) for n, o in enumerate(outs, 1) if (o.get("internal") or {}).get("model_error")]
        alarm = ("🔴 Ошибка связи с моделью: " + "; ".join(f"п. {n} — {e}" for n, e in me) + " → инженеру без разбора\n") if me else ""
        es = [str(n) for n, o in enumerate(outs, 1) if (o.get("internal") or {}).get("empty_search")]
        if es: alarm += f"⚠ Пустой поиск: п. {', '.join(es)} — модель не вызывалась\n"
        notify(f"{alarm}{head}{who} (id {uid})\nПунктов: {len(outs)} · Данные проекта: {doc_names(docs) if docs else 'нет'}\n"
               f"Покупателю: {routed(outs, 'client')} · Инженеру: {routed(outs, 'engineer')}\n{verdict_summary(outs)}\n"
               f"Время ответа: {round(time.time() - t0)} с")
    except Exception as e:
        log("ошибка", type(e).__name__); send_text(tok, uid, "Не получилось подготовить ответ. Попробуйте позже или передайте инженеру.")
        notify(f"🔴 Обработка упала: {type(e).__name__}\n{head}{who} (id {uid}) · файлов проекта: {len(docs or [])}\n"
               f"Покупателю ничего не ушло, {round(time.time() - t0)} с")

def flush(tok):
    for uid, p in list(PENDING.items()):   # 12.10: файлы без текста претензии не выбрасываем молча
        if time.time() - p["ts"] > KP_HOLD:
            PENDING.pop(uid); log("файлы проекта отпущены без претензии", uid)
            notify(f"{WHO.get(uid) or 'без имени'} (id {uid})\nДанные проекта получены, текста замечания не было "
                   f"{KP_HOLD // 60} мин — файлы отпущены")
    for uid, r in list(REDO.items()):   # 15.10: окно досылки истекло — один повторный разбор по всем файлам
        if time.time() - r["ts"] > DOC_WAIT:
            REDO.pop(uid); process(tok, uid, r["text"], r["docs"], redo=True)
    for uid, a in list(ANSWERED.items()):
        if time.time() - a["ts"] > KP_HOLD: ANSWERED.pop(uid)
    for key, a in list(ASKS.items()):   # 20.10: кнопку так и не нажали
        if time.time() - a["ts"] > KP_HOLD:
            ASKS.pop(key); log("файл без ответа на кнопки отпущен", a["uid"])
            notify(f"{WHO.get(a['uid']) or 'без имени'} (id {a['uid']})\nФайл «{a['name']}» не распознан, кнопку не нажали "
                   f"{KP_HOLD // 60} мин — отпущен")
    notify_retry()

OCR_NOTE = "Распознаю скан — это 1–2 минуты."

def scan_pending(paths):
    """21.10: есть скан без готового распознавания — распознавание сейчас в цикле бота (вынести в фон — отдельной задачей)."""
    try:
        import project_docs as PD
        return any(PD.needs_ocr(p) for p in paths)
    except Exception: return False

# 21.10 (Прил. 1, п. 2.5): сводка с разбивкой по типам вердикта (Прил. 1, п. 2.4) — те же названия, что в договоре
VERDICT_NAMES = [(1, "подтверждается нормативом"), (2, "опровергается"), (3, "встречный вопрос"),
                 (4, "вне зоны ответственности"), (5, "основания не найдено")]

def verdict_summary(outs):
    """«По типам вердикта: подтверждается нормативом — 1, …» (все пять, включая нули) + «без вердикта — N», если есть
    пункты, где вердикт не вынесен (блок проверки, сбой модели, пустой поиск). Вердикт — после проверки (internal.verdict)."""
    vs = [(o.get("internal") or {}).get("verdict") for o in outs if isinstance(o, dict)]
    line = "По типам вердикта: " + ", ".join(f"{name} — {sum(1 for v in vs if v == k)}" for k, name in VERDICT_NAMES)
    none = sum(1 for v in vs if v not in dict(VERDICT_NAMES))
    return line + (f", без вердикта (проверка не пройдена) — {none}" if none else "") + "."

SETTINGS_USERS = EF.ints("SETTINGS_USERS")

def settings_cmd(uid, text):
    """21.10 (Прил. 1, п. 2.5): /ирония 0|1|2, /тон деловой|мягкий, /настройки — только сотрудникам из settings_users."""
    import answer as A
    cmd, _, arg = text.strip().partition(" "); arg = arg.strip().lower(); cur = A.style()
    show = lambda st: f"Сейчас: ирония {st['irony']} из 2, тон «{st['tone']}»."
    if cmd == "/настройки": return show(cur) + " Изменить: /ирония 0, 1 или 2; /тон деловой или мягкий."
    if uid not in SETTINGS_USERS: return "Менять тон и иронию могут только сотрудники из списка настроек. " + show(cur)
    if cmd == "/ирония" and arg in ("0", "1", "2"): cur["irony"] = int(arg)
    elif cmd == "/тон" and arg in A.TONES: cur["tone"] = arg
    else: return "Не понял. /ирония 0, 1 или 2; /тон деловой или мягкий; /настройки — посмотреть."
    rec = dict(cur, updated_by=uid, updated_at=time.strftime("%F %T", time.gmtime()))
    tmp = A.SETTINGS + ".tmp"; json.dump(rec, open(tmp, "w", encoding="utf-8"), ensure_ascii=False); os.replace(tmp, A.SETTINGS)
    log("настройки изменены", uid, cur); notify(f"⚙ {WHO.get(uid) or uid} изменил настройки ответа: ирония {cur['irony']}, тон «{cur['tone']}»")
    return "Готово. " + show(cur) + " Действует на следующие ответы."

def doc_kind(path):
    """20.10: вид файла данных проекта (КП / опросный лист / расчёт) или None. Только PDF; ошибка разбора — None, не падение
    (14.10 одностраничный PDF уронил разбор КП)."""
    if not path.lower().endswith(".pdf"): return None
    try:
        import project_docs as PD
        return PD.kind(path)
    except Exception as e:
        log("вид файла не определён:", type(e).__name__); return None

def ask_kind(tok, uid, path, name):
    """20.10: нераспознанный файл — спросить кнопками: «Это претензия» / «Это данные проекта»."""
    import secrets
    key = secrets.token_hex(4); ASKS[key] = {"uid": uid, "path": path, "name": name, "ts": time.time()}
    call("POST", "/messages", tok, {"text": f"Файл «{name}» не похож на КП, опросный лист или теплотехнический расчёт. Что это?",
                                    "attachments": [{"type": "inline_keyboard", "payload": {"buttons": [[
                                        {"type": "callback", "text": "Это претензия", "payload": f"claim:{key}"},
                                        {"type": "callback", "text": "Это данные проекта", "payload": f"data:{key}"}]]}}]},
         {"user_id": uid})
    log("спросил вид файла", uid, key)

def project_files(tok, uid, text, got):
    """Файлы данных проекта — как до 20.10: с текстом — разбор; досылка — в окно; после ответа без них — повтор; иначе — ждём текст."""
    if text: PENDING.pop(uid, None); REDO.pop(uid, None); process(tok, uid, text, got)
    elif REDO.get(uid):   # досылка к уже отвеченной претензии — окно открывается заново
        r = REDO[uid]; r["docs"] = (r["docs"] + got)[:MAX_DOCS]; r["ts"] = time.time()
        send_text(tok, uid, f"Получил: {doc_names(got)}. Переделаю ответ по всем присланным файлам.")
    elif ANSWERED.get(uid) and time.time() - ANSWERED[uid]["ts"] <= KP_HOLD:
        REDO[uid] = {"text": ANSWERED.pop(uid)["text"], "docs": got, "ts": time.time()}
        send_text(tok, uid, f"Получил: {doc_names(got)}. Если есть ещё файлы по этому объекту — пришлите в течение "
                            f"{DOC_WAIT} секунд, переделаю ответ сразу по всем.")
    else:
        pend = PENDING.setdefault(uid, {"docs": [], "ts": time.time()})
        pend["docs"] = (pend["docs"] + got)[:MAX_DOCS]; pend["ts"] = time.time()
        send_text(tok, uid, f"Получил: {doc_names(got)}. Пришлите текст замечания — отвечу по этому проекту "
                            f"(файлы храню {KP_HOLD // 60} минут).")

def process_claim_file(tok, uid, path, name):
    """20.10: претензия файлом → пункты по разделам → разбор ВСЕХ пунктов частями по MAX_CLAIMS (ничего не отбрасываем).
    Повторный разбор «по данным проекта в течение 30 минут» к такой претензии не привязываем (ANSWERED не ставится)."""
    import claim_doc as C
    t0 = time.time(); who = WHO.get(uid) or "без имени"
    try:
        pts = C.points(C.extract_text(path))
        if not pts:
            send_text(tok, uid, "В файле не нашёл разделов с замечаниями. Пришлите претензию текстом."); log("претензия файлом: пунктов 0", uid); return
        parts = [pts[i:i + MAX_CLAIMS] for i in range(0, len(pts), MAX_CLAIMS)]
        send_text(tok, uid, f"Принял файл «{name}» как претензию: пунктов {len(pts)}" + (f", разберу частями ({len(parts)})" if len(parts) > 1 else "")
                  + ". Обычно до минуты на пункт.")
        log("претензия файлом", uid, "пунктов", len(pts), "частей", len(parts))
        allouts = []
        for k, chunk in enumerate(parts, 1):
            paths, summary, outs = handle(None, None, False, claims=chunk, first=1 + (k - 1) * MAX_CLAIMS, part=(k, len(parts)) if len(parts) > 1 else None)
            send_text(tok, uid, summary)
            for p_ in paths: send_file(tok, uid, p_, "")
            allouts += outs
        if len(parts) > 1: send_text(tok, uid, f"Итого по файлу: пунктов {len(allouts)}. " + verdict_summary(allouts))   # 21.10
        log("ответ по претензии-файлу", uid, "пунктов", len(allouts))
        notify(f"📄 Претензия файлом\n{who} (id {uid})\nПунктов: {len(allouts)} (частей {len(parts)})\n"
               f"Покупателю: {routed(allouts, 'client')} · Инженеру: {routed(allouts, 'engineer')}\n{verdict_summary(allouts)}\nВремя ответа: {round(time.time() - t0)} с")
    except Exception as e:
        log("ошибка претензии-файла", type(e).__name__); send_text(tok, uid, "Не получилось разобрать файл. Пришлите претензию текстом.")
        notify(f"🔴 Претензия файлом — обработка упала: {type(e).__name__}\n{who} (id {uid})\nПокупателю ничего не ушло")

def on_callback(tok, u):
    """20.10: нажатие кнопки «Это претензия» / «Это данные проекта» (событие message_callback)."""
    cb = u.get("callback") or {}; user = cb.get("user") or u.get("user") or {}; uid = user.get("user_id")
    payload = str(cb.get("payload") or ""); kind_, _, key = payload.partition(":"); a = ASKS.get(key)
    # 20.10: формат события в документации MAX описан не полностью — пишем, ЧТО пришло (имена полей и payload, без имён людей)
    log("нажатие кнопки, формат:", json.dumps({"update": sorted(u), "callback": sorted(cb), "user": sorted(user),
                                              "payload": payload[:40], "callback_id": bool(cb.get("callback_id"))}, ensure_ascii=False))
    def answer(t):
        try: call("POST", "/answers", tok, {"message": {"text": t, "attachments": []}}, {"callback_id": cb.get("callback_id")})
        except Exception as e: log("ответ на кнопку не ушёл:", type(e).__name__)
    if not a or a["uid"] != uid or kind_ not in ("claim", "data"):
        answer("Кнопка устарела — пришлите файл ещё раз."); log("кнопка без ожидания", uid, payload[:20]); return
    ASKS.pop(key)
    if kind_ == "claim":
        answer(f"«{a['name']}» — претензия. Разбираю."); process_claim_file(tok, uid, a["path"], a["name"])
    else:
        answer(f"«{a['name']}» — данные проекта."); project_files(tok, uid, "", [a["path"]])

def poll_once(tok, marker):
    """Один long-poll: обработать пачку событий, вернуть новый маркер. 09.10: доступ по запросу Вадиму, приём КП (PDF)."""
    params = {"timeout": 15, "types": "message_created,bot_started,message_callback"}
    if marker: params["marker"] = marker
    d = call("GET", "/updates", tok, params=params)
    for u in d.get("updates", []):
        if u.get("update_type") == "message_callback":   # 20.10: кнопки «претензия / данные проекта»
            cu = (u.get("callback") or {}).get("user") or u.get("user") or {}
            if cu.get("user_id") is not None and allowed(cu.get("user_id")): on_callback(tok, u)
            continue
        m = u.get("message") or {}; user = (m.get("sender") or u.get("user") or {}); uid = user.get("user_id")
        if uid is None or user.get("is_bot"): continue
        WHO[uid] = who_str(user)
        if not allowed(uid):
            sent = ask_admin(user)
            send_text(tok, uid, "Запрос на доступ отправлен администратору." if sent else "Запрос на доступ уже отправлен, ждите.")
            log("запрос доступа", uid); continue
        body = m.get("body") or {}; text = (body.get("text") or "").strip()
        files = [a for a in (body.get("attachments") or []) if a.get("type") == "file"]
        if files:
            docs_ = [a for a in files if str(a.get("filename") or "").lower().endswith(DOC_EXT)]
            if not docs_:
                send_text(tok, uid, "Пришлите файл в PDF, DOCX или ODT: претензию или данные проекта (КП, опросный лист, "
                                    "теплотехнический расчёт)."); continue
            got = [(download_file(tok, (a.get("payload") or {}).get("url"), a.get("filename")), str(a.get("filename") or "файл"))
                   for a in docs_[:MAX_DOCS]]
            known = [p_ for p_, _ in got if doc_kind(p_)]   # 20.10: распознанные — как раньше; остальные — спросить кнопками
            for p_, name in got:
                if p_ not in known: ask_kind(tok, uid, p_, name)
            if known: project_files(tok, uid, text, known)
            elif text: process(tok, uid, text, None)   # текст к нераспознанному файлу — разбираем текст, файл ждёт кнопки
            continue
        if text.split(" ")[0] in ("/ирония", "/тон", "/настройки"):   # 21.10: настройка тона и иронии
            send_text(tok, uid, settings_cmd(uid, text)); continue
        if u.get("update_type") == "bot_started" or text in ("", "/start", "/help"):
            send_text(tok, uid, START + "\n\n" + HELP); continue
        if len(text) < SHORT_MAX and not CONSTR.search(text):   # 20.10: «1», «ок», «привет» — подсказка, без разбора
            send_text(tok, uid, SHORT_HINT); log("короткое сообщение — подсказка", uid, "символов", len(text)); continue
        pend = PENDING.get(uid)
        if pend and pend.get("docs") and time.time() - pend["ts"] <= KP_HOLD:
            PENDING.pop(uid); process(tok, uid, text, pend["docs"]); continue
        if REDO.get(uid):   # пришёл новый текст, пока ждали досылку файлов — отвечаем по нему с теми же файлами
            r = REDO.pop(uid); process(tok, uid, text, r["docs"]); continue
        log("запрос от", uid, "символов", len(text))
        process(tok, uid, text, None)   # 12.10: отвечаем сразу; данные проекта в течение 30 мин → повторный разбор
    flush(tok)
    if d.get("marker"):
        marker = str(d["marker"]); open(STATE, "w").write(marker)
    return marker

if __name__ == "__main__":
    main()
