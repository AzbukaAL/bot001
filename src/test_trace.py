"""П-9/П-12 (17.10.2026): трасса пункта, журнал вызовов (в т. ч. неудачных), сбой журнала не ломает вызов, строка расхода.
  python3 src/test_trace.py"""
import datetime, io, json, os, sys, tempfile, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
import answer as A, daily_cost as DC

ok = 0; fail = []
def check(name, cond):
    global ok
    if cond: ok += 1
    else: fail.append(name)

class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()

tmp = tempfile.mkdtemp(); A.CALLS_LOG = f"{tmp}/calls.jsonl"; real = urllib.request.urlopen; A.time.sleep = lambda s: None
seq = []
def fake(req, *a, **kw):
    x = seq.pop(0)
    if isinstance(x, Exception): raise x
    return Resp(json.dumps({"choices": [{"message": {"content": '{"stance": "за покупателя"}'}}],
                            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "cost_rub": x}}).encode())
urllib.request.urlopen = fake

A.TRACE.clear(); seq[:] = [urllib.error.URLError("сбой"), 1.25]
t, u = A.chat(A.JUDGE_SYS, "x", 50, role="mechanical")
rows = [json.loads(l) for l in open(A.CALLS_LOG, encoding="utf-8")]
check("неудачная попытка в журнале", [r["status"] for r in rows] == ["failed", "ok"] and rows[0]["err"] == "URLError")
check("шаг и роль", rows[1]["step"] == "judge" and rows[1]["role"] == "mechanical" and rows[1]["attempt"] == 2)
check("модель и версия промпта", rows[1]["model"] == A.llm_roles.model("mechanical") and rows[1]["prompt"] == A.prompt_ver(A.JUDGE_SYS))
check("₽ из cost_rub", rows[1]["rub"] == 1.25 and rows[1]["tin"] == 100)
tr = A.trace(3.0)
check("трасса: попытки, ₽, сбои", tr["attempts"] == {"judge": 2} and tr["rub"] == 1.25 and tr["failed"] == 1 and tr["sec"] == 3.0)

A.CALLS_LOG = "/proc/нельзя/calls.jsonl"; seq[:] = [0.5]
try: A.chat(A.JUDGE_SYS, "x", 50, role="mechanical"); check("сбой журнала не ломает вызов", True)
except Exception: check("сбой журнала не ломает вызов", False)

A.NUMS.clear(); A.NUMS.extend([2, 1, 0])
check("числа: переписано и к инженеру", A.trace(0)["numbers"] == {"checks": 3, "rewritten": 3, "to_engineer": 0})
check("метка числа ловится", bool(A.NUM_PROB.match("число 32 — нет ни в цитате, ни в расчёте, ни в претензии")))

now = datetime.datetime(2026, 10, 17, 14, 0, 0); log = f"{tmp}/day.jsonl"
with open(log, "w") as f:
    for ts, src, rub, st in [("2026-10-16 13:59:59", "bot_max.py", 9, "ok"), ("2026-10-16 14:00:00", "bot_max.py", 2.4, "ok"),
                             ("2026-10-17 09:00:00", "mvp_runs3.py", 30, "ok"), ("2026-10-17 10:00:00", "bot_max.py", 0, "failed"),
                             ("2026-10-17 14:00:00", "bot_max.py", 7, "ok")]:
        f.write(json.dumps({"ts": ts, "src": src, "rub": rub, "status": st}) + "\n")
s = DC.line(now, log, tmp)
check("строка: окно 24 ч и разбивка", "32 ₽ — бот 2 ₽" in s and "прогоны 30 ₽" in s and "вызовов 3" in s and "сбоев 1" in s)
check("нет журнала — 🔴, не 0 ₽", DC.line(now, f"{tmp}/нет.jsonl", tmp).startswith("🔴") and "0 ₽" not in DC.line(now, f"{tmp}/нет.jsonl", tmp))
open(f"{tmp}/bad.jsonl", "w").write("{не json\n")
check("битый журнал — 🔴", DC.line(now, f"{tmp}/bad.jsonl", tmp).startswith("🔴"))
urllib.request.urlopen = real
print(f"трасса и журнал: {ok}/{ok + len(fail)}", "" if not fail else f"ПРОВАЛ: {fail}")
sys.exit(1 if fail else 0)
