"""Тест бота MAX на поддельном API (без токенов и без вызовов модели), 09.10.2026: доступ по запросу Вадиму (в Telegram через
@vadim_sbrain_bot, кнопки-ссылки mok_/mno_ на Telegram-бота), справка, приём данных проекта (PDF: подписью / следом), скачивание
вложения (без токена, на 403 — с токеном), повтор при attachment.not.ready, маркер.
15.10.2026: к одной претензии — несколько файлов проекта (КП, опросный лист, теплотехнический расчёт), досылка в окне DOC_WAIT
даёт ОДИН повторный разбор по всем файлам.
  python3 src/test_bot_fake.py
"""
import json, urllib.error, os, re, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код

LOG, QUEUE, NOT_READY, DL = [], [], {"n": 1}, {"noauth": 0, "auth": 0}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj=None, raw=None):
        b = raw if raw is not None else json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        LOG.append(("GET", self.path, self.headers.get("Authorization"), b""))
        if self.path.startswith("/files/"):   # вложение: без токена — 403, с токеном — файл
            if not self.headers.get("Authorization"): DL["noauth"] += 1; return self._send(403, {})
            DL["auth"] += 1; return self._send(200, raw=b"%PDF-1.4 fake kp")
        return self._send(200, {"updates": QUEUE.pop(0) if QUEUE else [], "marker": 42})
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n)
        LOG.append(("POST", self.path, self.headers.get("Authorization"), body))
        if self.path.startswith("/bot"): return self._send(200, {"ok": True, "result": {"message_id": 1}})   # Telegram (sbrain)
        if self.path.startswith("/uploads"): return self._send(200, {"url": f"http://127.0.0.1:{PORT}/upload-here"})
        if self.path.startswith("/upload-here"): return self._send(200, {"token": "FILETOKEN"})
        if self.path.startswith("/messages") and b"attachments" in body and NOT_READY["n"] > 0:
            NOT_READY["n"] -= 1; return self._send(400, {"code": "attachment.not.ready"})
        self._send(200, {"message": {}})

srv = HTTPServer(("127.0.0.1", 0), H); PORT = srv.server_port
threading.Thread(target=srv.serve_forever, daemon=True).start()
tmp = tempfile.mkdtemp(); open(f"{tmp}/notify", "w").write("NOTIFYTOKEN")
os.environ.update(CS_MAX_API=f"http://127.0.0.1:{PORT}", CS_TG_API=f"http://127.0.0.1:{PORT}", CS_TG_NOTIFY=f"{tmp}/notify",
                  CS_MAX_ACCESS=f"{tmp}/access.json", CS_MAX_KP=f"{tmp}/kp")
import bot_max as B
B.ALLOWED = set(); B.STATE = f"{tmp}/marker"; B.time.sleep = lambda s: None
doc = f"{tmp}/x.docx"; open(doc, "wb").write(b"PK fake docx")
HANDLED, REDOS, DOCS = [], [], []
def fake_handle(text, docs=None, redo=False):
    HANDLED.append((text, bool(docs))); REDOS.append((text, redo)); DOCS.append(list(docs or [])); return [doc], "Пунктов 1.", [{}]
B.handle = fake_handle
B.doc_kind = lambda p: "КП"   # 20.10: поддельные PDF теста — данные проекта (прежний путь); новый путь — test_claim_file.py
B.SHORT_MAX = 0   # 20.10: заглушки «претензия А» короче 15 символов — подсказку проверяет test_claim_file.py

def mc(uid, text="", att=None):
    body = {"text": text}
    if att: body["attachments"] = [att]
    return {"update_type": "message_created", "message": {"sender": {"user_id": uid, "name": "Тестов"}, "body": body}}
pdf = {"type": "file", "filename": "kp.pdf", "payload": {"url": f"http://127.0.0.1:{PORT}/files/kp.pdf"}}
pdf2 = {"type": "file", "filename": "teplo.pdf", "payload": {"url": f"http://127.0.0.1:{PORT}/files/teplo.pdf"}}
def mc2(uid, text="", atts=()):   # сообщение с несколькими вложениями
    return {"update_type": "message_created",
            "message": {"sender": {"user_id": uid, "name": "Тестов"}, "body": {"text": text, "attachments": list(atts)}}}
marker = None
def step(*ups):
    global marker; QUEUE.append(list(ups)); marker = B.poll_once("TESTTOKEN", marker)

step(mc(999, "привет"))                       # неизвестный → запрос Вадиму
step(mc(999, "ещё раз"))                      # повтор — без второго запроса
acc = B.load_access(); code = next(iter(acc["pending"]))
acc["allowed"]["111"] = {"who": "x"}; B.save_access(acc)   # так делает Telegram-бот после «Да»
step({"update_type": "bot_started", "user": {"user_id": 111}})
step(mc(111, "1. претензия без КП"))  # 12.10: без КП → ответ сразу, без ожидания
step(mc(111, "претензия А"))                  # ожидания нет: ответ в том же опросе, хотя WAIT=120
imm = ("претензия А", False) in HANDLED and 111 not in B.PENDING
B.DOC_WAIT = 0                                # окно досылки в тесте не ждём
step(mc(111, "", pdf))                        # файл в течение 30 мин → повторный разбор той же претензии
step(mc(111, "претензия Б", pdf))                                # КП с подписью
step(mc(111, "", {"type": "file", "filename": "photo.jpg", "payload": {"url": "http://x"}}))
def boom(text, docs=None, redo=False): raise ValueError("падение внутри разбора")
B.handle = boom; step(mc(111, "претензия В"))   # обработка падает → алерт Вадиму
B.handle = fake_handle
_tg_send = B.tg_send
def tg_dead(body): raise urllib.error.URLError("канал уведомлений мёртв")
B.tg_send = tg_dead; step(mc(111, "претензия Г"))   # уведомление не уходит → ответ покупателю всё равно уходит
B.tg_send = _tg_send
# 12.10: КП без текста претензии — одно сообщение сразу, хранение KP_HOLD, не молчаливый выброс
B.PENDING.clear(); B.ANSWERED.clear()
step(mc(111, "", pdf))                  # КП без текста → одно сообщение «Получил КП…»
kp_held = 111 in B.PENDING
step()                                  # ещё один опрос — второго сообщения быть не должно
kp_msgs = [json.loads(x[3]).get("text") for x in LOG if x[0] == "POST" and x[1].startswith("/messages")
           and b'"text"' in x[3] and (json.loads(x[3]).get("text") or "").startswith("Получил: файл неизвестного вида. Пришлите")]
step(mc(111, "претензия Д"))            # текст позже 2 минут → разбор С КП
B.PENDING.clear(); B.ANSWERED.clear(); B.KP_HOLD = 0
step(mc(111, "", pdf))          # срок хранения вышел → файлы отпущены + уведомление
kp_released = 111 not in B.PENDING
B.KP_HOLD = 1800
# 15.10: два файла в одном сообщении вместе с текстом
B.PENDING.clear(); B.ANSWERED.clear(); B.REDO.clear()
step(mc2(111, "претензия Е", (pdf, pdf2)))
two_at_once = len(DOCS[-1]) == 2
# 15.10: ответ без данных проекта → два файла по одному в окне досылки → ОДИН повторный разбор по обоим
B.PENDING.clear(); B.ANSWERED.clear(); B.REDO.clear(); B.DOC_WAIT = 1800
step(mc(111, "претензия Ж"))                  # ответ без данных проекта
n_before = len(HANDLED)
step(mc(111, "", pdf))                        # первый файл — ждём досылку, разбора нет
step(mc(111, "", pdf2))                       # второй файл — окно открылось заново, разбора по-прежнему нет
window_holds = len(HANDLED) == n_before and len(B.REDO[111]["docs"]) == 2
B.DOC_WAIT = 0; step()                        # окно истекло → один повтор по двум файлам
one_redo = len(HANDLED) == n_before + 1 and len(DOCS[-1]) == 2 and REDOS[-1] == ("претензия Ж", True)

tg = [json.loads(x[3]) for x in LOG if x[0] == "POST" and x[1].startswith("/botNOTIFYTOKEN/sendMessage")]
ask = [m for m in tg if "пустить" in (m.get("text") or "")]
note = [m.get("text") or "" for m in tg if (m.get("text") or "").startswith("Капитан Сэм / MAX")]
msgs = [(x[1], json.loads(x[3]).get("text")) for x in LOG if x[0] == "POST" and x[1].startswith("/messages") and b'"text"' in x[3]]
razbor = [t for t in note if "Пунктов:" in t]
alert = [t for t in note if "Обработка упала" in t]
# пометка «по проекту (КП от …)» — у самой формы (handle в тестах подменён)
import zipfile, answer_docx as D
MARK = "Ответ по проекту (опросный лист от 09.10.2026; теплотехнический расчёт от 15.10.2026)"
_p = f"{tmp}/mark.docx"
D.render([{"claim": "замечание", "conclusion": "Вывод", "reasoning": "рассуждение", "basis": [], "calc": None,
           "action": None, "clarify": None}], _p, mark=MARK)
mark_in_docx = MARK in zipfile.ZipFile(_p).read("word/document.xml").decode("utf-8")
to = lambda uid: [t for p, t in msgs if f"user_id={uid}" in p]
checks = {
    "неизвестному — «запрос отправлен», Вадиму — запрос с кнопками на Telegram-бота": len(ask) == 1 and "пустить Тестов?" in ask[0]["text"]
        and f"start=mok_{code}" in json.dumps(ask[0]) and to(999)[0].startswith("Запрос на доступ отправлен"),
    "повтор — без второго запроса": len(ask) == 1 and to(999)[1].startswith("Запрос на доступ уже"),
    "допущенному — /start → «Присылайте претензию без ФИО…»": any(t and t.startswith("Присылайте претензию без ФИО") for t in to(111)),
    "текст без КП → ответ сразу, без ожидания КП": imm and ("1. претензия без КП", False) in HANDLED,
    "в сводке — приглашение прислать данные проекта (три вида, можно несколько)":
        B.KP_HINT.startswith("Если есть данные проекта — пришлите PDF: КП, опросный лист или теплотехнический расчёт")
        and "несколько файлов" in B.KP_HINT,
    "файл после ответа → повторный разбор той же претензии с данными проекта": ("претензия А", True) in HANDLED
        and ("претензия А", True) in REDOS and len([t for t in note if "🔁 Повтор с данными проекта" in t]) == 2,
    "два файла в одном сообщении с текстом → разбор по обоим": two_at_once,
    "досылка в окне DOC_WAIT не плодит разборы": window_holds,
    "после окна — ОДИН повтор по всем присланным файлам": one_redo,
    "повтор помечает docx «по проекту (<источники с датами>)»": mark_in_docx,
    "PDF с подписью → ответ с КП": ("претензия Б", True) in HANDLED,
    "не PDF/DOCX/ODT → просим файл в этих форматах": "Пришлите файл в PDF, DOCX или ODT: претензию или данные проекта (КП, опросный лист, теплотехнический расчёт)." in to(111),
    "вложение: без токена 403 → с токеном": DL["noauth"] >= 1 and DL["auth"] >= 1,
    "файл отправлен с токеном вложения (с повтором not.ready)": any(b"FILETOKEN" in x[3] for x in LOG if x[1].startswith("/messages")),
    "файлы проекта сохранены с правами 600": all(oct(os.stat(os.path.join(f"{tmp}/kp", f)).st_mode)[-3:] == "600" for f in os.listdir(f"{tmp}/kp")),
    "маркер сохранён": open(B.STATE).read() == "42",
    "уведомление на каждое обращение (8 разборов + падение + отпущенные файлы)":
        len(razbor) == 8 and len(note) == 10,
    "в уведомлении кто, пункты, данные проекта, маршруты, время": all(
        "Тестов" in t and "id 111" in t and "Пунктов: 1" in t and "Покупателю: 0 · Инженеру: 0" in t and "Время ответа:" in t
        for t in razbor) and len([t for t in razbor if "Данные проекта: нет" in t]) == 3
        and len([t for t in razbor if "Данные проекта: файл неизвестного вида" in t]) == 5,
    "в уведомлении нет текста претензии": not any(
        c in t for t in note for c in ("претензия без КП", "претензия А", "претензия Б", "претензия В", "претензия Г",
                                       "претензия Д", "претензия Е", "претензия Ж")),
    "обработка упала → алерт сразу": len(alert) == 1 and "ValueError" in alert[0]
        and "Покупателю ничего не ушло" in alert[0],
    "осечка уведомления не ломает ответ покупателю": ("претензия Г", False) in HANDLED
        and len([t for p, t in msgs if t == "Пунктов 1."]) == 9 and len(razbor) == 8,
    "файл без текста: ровно одно сообщение со сроком, файл не выброшен": kp_held and kp_msgs ==
        ["Получил: файл неизвестного вида. Пришлите текст замечания — отвечу по этому проекту (файлы храню 30 минут)."],
    "текст позже 2 минут → разбор С КП": ("претензия Д", True) in HANDLED,
    "срок хранения файлов вышел → отпущены + уведомление": kp_released
        and len([t for t in note if "файлы отпущены" in t]) == 1,
}
for k, v in checks.items(): print(("✅ " if v else "❌ ") + k)
srv.shutdown(); sys.exit(0 if all(checks.values()) else 1)
