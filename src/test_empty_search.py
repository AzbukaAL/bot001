"""П-8 (17.10.2026): пустой поиск — явная причина и пункт инженеру без вызова модели; пустой индекс — ошибка на импорте.
  python3 src/test_empty_search.py"""
import os, re, subprocess, sys, tempfile, urllib.request, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import answer as A, bot_max as BM

ok = 0; fail = []
def check(name, cond):
    global ok
    if cond: ok += 1
    else: fail.append(name)

tmp = tempfile.mkdtemp(); A.CALLS_LOG = f"{tmp}/calls.jsonl"; BM.OUT = tmp
calls = []
def counted(req, *a, **kw): calls.append(1); raise AssertionError("модель не должна вызываться")
real = urllib.request.urlopen; urllib.request.urlopen = counted

for t in ("Привет", "ок, спасибо", "???"):
    calls.clear(); paths, summary, outs = BM.handle(t); i = outs[0]["internal"]
    check(f"«{t}»: модель не вызвана", not calls)
    check(f"«{t}»: инженеру с причиной", outs[0]["route"] == "engineer" and i.get("empty_search") and A.EMPTY_SEARCH in i["why_human"])
    check(f"«{t}»: строка сотруднику", "поиск не нашёл ни одной нормы" in summary)
doc = re.sub("<[^>]+>", "", zipfile.ZipFile(paths[0]).read("word/document.xml").decode())
check("причина в черновике", A.EMPTY_SEARCH in doc)

notes = []; BM.send_text = lambda *a: None; BM.send_file = lambda *a: None; BM.notify = notes.append
BM.process("tok", 1, "Привет")
check("Вадиму ⚠ пустой поиск", notes and notes[-1].startswith("⚠ Пустой поиск: п. 1"))
# пункт по существу — поиск не пуст, до модели доходит
calls.clear()
try: A.answer("Кровля из ондулина сорвёт ветром")
except Exception: pass
check("пункт по существу идёт в модель", bool(calls))
urllib.request.urlopen = real

for what in ("PTS", "REG"):
    r = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0,{ROOT + '/src'!r}); import run08 as R; "
                        f"R.{what} = type(R.{what})(); import answer"], capture_output=True, text=True)
    check(f"пустой {what} — ошибка на импорте", r.returncode != 0 and "индекс пуст" in r.stderr)
print(f"пустой поиск: {ok}/{ok + len(fail)}", "" if not fail else f"ПРОВАЛ: {fail}")
sys.exit(1 if fail else 0)
