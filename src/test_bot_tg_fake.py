"""Тест бота Telegram на поддельном API (без токенов и без вызовов модели): доступ через запрос Вадиму, справка, docx.
  python3 src/test_bot_tg_fake.py
"""
import json, os, re, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код

CALLS, QUEUE = [], []
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):   # скачивание файла: /file/bot<tok>/<path>
        CALLS.append(("FILE", "download", {"path": self.path})); b = b"%PDF-1.4 fake kp"
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n)
        tok, method = re.match(r"/bot([^/]+)/(\w+)", self.path).groups()
        try: p = json.loads(body)
        except ValueError: p = {"_multipart": body}
        CALLS.append((tok, method, p))
        res = {"getMe": {"username": "captain_test_bot"}, "getUpdates": QUEUE.pop(0) if QUEUE else [],
               "getFile": {"file_path": "documents/kp.pdf"}}.get(method, {"message_id": 1})
        b = json.dumps({"ok": True, "result": res}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
tmp = tempfile.mkdtemp()
open(f"{tmp}/notify", "w").write("NOTIFYTOKEN")
os.environ.update(CS_TG_API=f"http://127.0.0.1:{srv.server_port}", CS_TG_NOTIFY=f"{tmp}/notify", CS_TG_KP=f"{tmp}/kp",
                  CS_TG_ACCESS=f"{tmp}/access.json", CS_TG_OFFSET=f"{tmp}/offset")
import bot_tg as T, bot_max as BM
doc = f"{tmp}/x.docx"; open(doc, "wb").write(b"PK fake")
doc2 = f"{tmp}/y.docx"; open(doc2, "wb").write(b"PK fake 2")
HANDLED = []
def fake_handle(text, kp=None):
    HANDLED.append((text, bool(kp))); return [doc, doc2], "Пунктов 2. Готово для покупателя — 1. На проверку инженеру — 1 (черновик во втором файле).", [{}, {}]
BM.handle = fake_handle
T.ADMIN = BM.TG_ADMIN = 424242   # 27.10: id администратора — из .env, в тесте свой
ADMIN, S, X = T.ADMIN, {"id": 555, "first_name": "Олег", "username": "stranger"}, {"id": 777, "first_name": "Чужой"}
def msg(i, u, text, chat_type="private"): return {"update_id": i, "message": {"from": u, "chat": {"id": u["id"], "type": chat_type}, "text": text}}
def docmsg(i, u, caption=None, mime="application/pdf", name="kp.pdf"):
    m = {"from": u, "chat": {"id": u["id"], "type": "private"}, "document": {"file_id": "F1", "file_name": name, "mime_type": mime}}
    if caption: m["caption"] = caption
    return {"update_id": i, "message": m}
def sent(tok=None, method="sendMessage", chat=None):
    return [p for t, m, p in CALLS if m == method and (tok is None or t == tok) and (chat is None or p.get("chat_id") == chat)]

off = None
def step(*ups):
    global off; QUEUE.append(list(ups)); off = T.poll_once("BOTTOKEN", "captain_test_bot", off)

step(msg(1, S, "/start"))
req = sent("NOTIFYTOKEN", chat=ADMIN)
code = re.search(r"start=ok_(\w+)", json.dumps(req)).group(1) if req else ""
step(msg(2, S, "/start"))
step(msg(3, X, f"/start ok_{code}"))
allowed_after_x = "555" in T.load()["allowed"]
step(msg(4, {"id": ADMIN, "first_name": "Вадим"}, f"/start ok_{code}"))
step(msg(5, S, "/start"))
T.WAIT = 0   # текст без КП: ответ без КП сразу по истечении ожидания
step(msg(6, S, "1. претензия"), msg(7, {"id": 888, "first_name": "Группа"}, "в группе", "group"))
T.WAIT = 120
step(msg(8, S, "претензия А")); step(docmsg(9, S))                                  # текст, потом КП
step(docmsg(10, S, caption="претензия Б"))                                          # КП с подписью
step(docmsg(11, S)); step(msg(12, S, "претензия В"))                                # КП, потом текст
step(docmsg(13, S, mime="image/jpeg", name="photo.jpg"))                                              # не PDF
# решение по доступу в MAX (запрос пришёл из бота MAX): чужой не может, Вадим — да → доступ + уведомление в MAX
os.environ["CS_MAX_ACCESS"] = f"{tmp}/max_access.json"; BM.ACCESS = f"{tmp}/max_access.json"
BM.save_access({"allowed": {}, "pending": {"abcd1234": {"user_id": 5001, "who": "Покупатель MAX", "ts": 0}}})
MAXSENT = []; BM.token = lambda: "MAXTOKEN"; BM.send_text = lambda tok, uid, text: MAXSENT.append((uid, text))
step(msg(14, X, "/start mok_abcd1234"))
max_after_x = "5001" in BM.load_access()["allowed"]
step(msg(15, {"id": ADMIN, "first_name": "Вадим"}, "/start mok_abcd1234"))

to_s = [p["text"] for p in sent("BOTTOKEN", chat=555)]
checks = {
    "запрос Вадиму через @vadim_sbrain_bot с кнопками Да/Нет": len(req) == 1 and "пустить Олег, @stranger" in req[0]["text"]
        and [b["text"] for b in req[0]["reply_markup"]["inline_keyboard"][0]] == ["Да", "Нет"],
    "неизвестному — «запрос отправлен», повтор — без второго запроса": to_s[0].startswith("Запрос на доступ отправлен")
        and to_s[1].startswith("Запрос на доступ уже") and len(sent("NOTIFYTOKEN")) == 1,
    "чужой не может одобрить": not allowed_after_x and any("администратор" in p["text"] for p in sent("BOTTOKEN", chat=777)),
    "после «Да» Вадима доступ открыт и пользователь уведомлён": "555" in T.load()["allowed"] and any(t.startswith("Доступ открыт") for t in to_s),
    "/start → «Присылайте претензию без ФИО…»": any(t.startswith("Присылайте претензию без ФИО, телефонов и адресов") for t in to_s),
    "претензия → сводка + два docx": any(t.startswith("Пунктов 2. Готово для покупателя") for t in to_s)
        and len(sent("BOTTOKEN", "sendDocument")) == 2 * len(HANDLED),
    "сообщение из группы проигнорировано": not sent(chat=888) and not sent("NOTIFYTOKEN", chat=888),
    "offset сохранён": open(f"{tmp}/offset").read() == "16",
    "MAX: чужой не может одобрить": not max_after_x,
    "MAX: «Да» Вадима → доступ открыт и уведомление в MAX": "5001" in BM.load_access()["allowed"] and any(u == 5001 and t.startswith("Доступ открыт") for u, t in MAXSENT),
    "текст без КП → ответ без КП (по истечении ожидания)": ("1. претензия", False) in HANDLED,
    "текст, затем PDF → ответ с КП": ("претензия А", True) in HANDLED,
    "PDF с подписью → ответ с КП сразу": ("претензия Б", True) in HANDLED,
    "PDF, затем текст → ответ с КП": ("претензия В", True) in HANDLED,
    "не PDF → «Пришлите КП объекта в PDF»": any(p.get("text") == "Пришлите КП объекта в PDF." for p in sent("BOTTOKEN", chat=555)),
    "КП скачан в каталог КП (600)": all(oct(os.stat(os.path.join(f"{tmp}/kp", f)).st_mode)[-3:] == "600" for f in os.listdir(f"{tmp}/kp")) and len(os.listdir(f"{tmp}/kp")) >= 1,
}
for k, v in checks.items(): print(("✅ " if v else "❌ ") + k)
srv.shutdown()
sys.exit(0 if all(checks.values()) else 1)
