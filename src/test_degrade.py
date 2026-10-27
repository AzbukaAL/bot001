"""CI-2 (П-5/П-7, 17.10.2026): модель выключена — результат не пустой, строка о недоступности есть, Вадиму 🔴.
  python3 src/test_degrade.py"""
import io, json, os, re, sys, zipfile, tempfile, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
import answer as A, bot_max as BM

ok = 0; fail = []
def check(name, cond):
    global ok
    if cond: ok += 1
    else: fail.append(name)

tmp = tempfile.mkdtemp(); A.CALLS_LOG = f"{tmp}/calls.jsonl"; BM.OUT = tmp; A.time.sleep = lambda s: None
CLAIM = "Вводной автомат 25 А мал: при 15 кВт на трёх фазах нужен 32 А."
real = urllib.request.urlopen
for name, exc in [("сеть", urllib.error.URLError("нет связи")),
                  ("модель снята (HTTP 404)", urllib.error.HTTPError("https://polza.ai", 404, "model not found", {}, io.BytesIO(b"")))]:
    calls = []
    def dead(req, *a, **kw):
        calls.append(1); raise exc
    urllib.request.urlopen = dead
    paths, summary, outs = BM.handle(CLAIM)
    o = outs[0]; i = o["internal"]
    check(f"{name}: пункт инженеру", o["route"] == "engineer" and len(outs) == 1)
    check(f"{name}: нормы из поиска не пустые", len(i.get("found") or []) >= 3 and all(f["quote"] for f in i["found"]))
    check(f"{name}: расчёт кодом есть", any("А" in l for l in o.get("calc") or []))
    check(f"{name}: причина — модель недоступна", "модель недоступна" in (i.get("why_human") or "") and i.get("model_error"))
    check(f"{name}: строка сотруднику", "Модель недоступна: по п. 1" in summary)
    check(f"{name}: черновик инженеру создан", any("chernovik_inzheneru" in p and os.path.getsize(p) > 0 for p in paths))
    doc = re.sub("<[^>]+>", "", zipfile.ZipFile(paths[0]).read("word/document.xml").decode())
    check(f"{name}: в docx причина, нормы и расчёт", all(k in doc for k in ("модель недоступна", "кандидат поиска", "22,8 А")))
    rows = [json.loads(l) for l in open(A.CALLS_LOG, encoding="utf-8")]
    check(f"{name}: сбои в журнале", rows and all(r["status"] == "failed" for r in rows))
    os.remove(A.CALLS_LOG)

# process(): Вадиму 🔴, сотруднику — ответ, а не «Не получилось»
sent, notes = [], []
BM.send_text = lambda tok, uid, t: sent.append(t); BM.send_file = lambda tok, uid, p, c: sent.append(p); BM.notify = notes.append
BM.process("tok", 1, CLAIM)
check("Вадиму 🔴 ошибка связи с моделью", notes and notes[-1].startswith("🔴 Ошибка связи с моделью: п. 1"))
check("сотруднику не «Не получилось»", not any("Не получилось" in str(t) for t in sent) and any("Модель недоступна" in str(t) for t in sent))
# ошибка нашего кода — по-прежнему «Обработка упала», а не деградация
orig = A._answer; A._answer = lambda *a, **k: 1 / 0
notes.clear(); sent.clear(); BM.process("tok", 1, CLAIM); A._answer = orig
check("ошибка кода — «Обработка упала»", notes and notes[-1].startswith("🔴 Обработка упала: ZeroDivisionError"))
urllib.request.urlopen = real
print(f"деградация: {ok}/{ok + len(fail)}", "" if not fail else f"ПРОВАЛ: {fail}")
sys.exit(1 if fail else 0)
