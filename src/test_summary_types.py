"""Сводка в боте с разбивкой по типам вердикта (21.10.2026, Прил. 1, п. 2.5).  python3 src/test_summary_types.py"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot_max as B

ok = 0; fail = []
def check(name, cond):
    global ok
    if cond: ok += 1
    else: fail.append(name)
O = lambda v: {"route": "engineer", "internal": {"verdict": v}}
s = B.verdict_summary([O(1), O(2), O(2), O(3), O(4), O(5), O(None)])
check("все пять типов с числами", s.startswith("По типам вердикта: подтверждается нормативом — 1, опровергается — 2, встречный вопрос — 1, "
      "вне зоны ответственности — 1, основания не найдено — 1"))
check("без вердикта — отдельно", "без вердикта (проверка не пройдена) — 1" in s)
check("нули тоже показаны, «без вердикта» — только если есть", B.verdict_summary([O(2)]) == "По типам вердикта: подтверждается нормативом — 0, "
      "опровергается — 1, встречный вопрос — 0, вне зоны ответственности — 0, основания не найдено — 0.")
check("названия — как в Прил. 1, п. 2.4", [n for _, n in B.VERDICT_NAMES] == ["подтверждается нормативом", "опровергается", "встречный вопрос",
      "вне зоны ответственности", "основания не найдено"])
# handle: строка в сводке сотруднику (модель подменена на готовые ответы — без сети)
import answer as A
A.answer = lambda c, obj=None: ({"claim": c, "mapping": {}, "route": "engineer", "conclusion": None, "short": None, "reasoning": A.ENGINEER,
                                 "action": None, "clarify": None, "basis": [], "calc": [], "trace": {},
                                 "internal": {"verdict": 3 if "дверь" in c else 5, "raw_verdict": 3, "status": "ok", "fear": None, "found": [],
                                              "why_human": "x", "engineer_why": "x", "draft": {}, "draft_basis": []}}, [])
B.OUT = tempfile.mkdtemp()
paths, summary, outs = B.handle("1. Входная дверь будет промерзать\n2. Нет снегозадержателей на кровле")
check("в сводке сотруднику — разбивка по типам", "По типам вердикта: подтверждается нормативом — 0, опровергается — 0, встречный вопрос — 1, "
      "вне зоны ответственности — 0, основания не найдено — 1." in summary)
print(f"сводка по типам вердикта: {ok}/{ok + len(fail)}", "" if not fail else f"ПРОВАЛ: {fail}")
sys.exit(1 if fail else 0)
