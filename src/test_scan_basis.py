"""Данные проекта со скана (21.10.2026, решение Вадима): идут в рассуждение и в черновик инженеру с пометкой «скан — сверить»,
покупателю — нет (ссылка в тексте — пункт инженеру). Модель подменена.  python3 src/test_scan_basis.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import answer as A

ok = 0; fail = []
def check(name, cond):
    global ok
    if cond: ok += 1
    else: fail.append(name)

OBJ = {"label": "Данные Вашего проекта", "items": [
    {"id": "S1", "позиция": "Утепление внешних стен 1-го этажа", "описание": "Каменная вата. 150 мм плитный плотность 33 кг/куб.м", "ocr": True,
     "источник_метка": "техническое описание от 23.03.2026"},
    {"id": "T1", "позиция": "Окна и двери: изделие 2 (окно)", "описание": "профиль 70; заполнение 4M1-12-4M1-8-4M1", "ocr": False,
     "источник_метка": "спецификация окон от 23.03.2026"}]}
NORM = {"ref": "СП 50.13330.2024|п.5.1", "label": "СП 50", "label_engineer": "СП 50", "quote": "Приведённое сопротивление теплопередаче ограждающих конструкций должно быть не менее нормируемого.",
        "standard": False, "client_ok": True, "mark": None}
orig = (A.analyze, A.select_basis, A.write, A.judge)
A.analyze = lambda c, *a: {"claim": c, "mapping": {}, "verdict": 2, "status": "ok", "direct": NORM["ref"], "evidence": "", "cite": [NORM["ref"]],
                           "reason": "x", "counter_question": None, "usage": {}, "raw_verdict": 2, "norm_ids": [NORM["ref"]], "sk_ids": []}
A.select_basis = lambda a: ([dict(NORM)], [], {})
seen = []
def write(a, basis, calc, concl, extra=""):
    seen.append([(b["ref"], b.get("mark")) for b in basis]); scan_n = next(k for k, b in enumerate(basis, 1) if b.get("mark") == A.SCAN_MARK) if any(b.get("mark") == A.SCAN_MARK for b in basis) else None
    t = f"В Вашем проекте стены утеплены каменной ватой 150 мм [{scan_n}]." if (MODE[0] == "scan" and scan_n) else "Сопротивление теплопередаче должно быть не менее нормируемого [1]."
    return {"conclusion": "Претензия не подтверждается", "short": t, "reasoning": t, "action": None, "clarify": None}, {}
A.write = write
A.judge = lambda *a, **k: ({"stance": "против покупателя", "addresses": True, "formal": False}, {})
MODE = ["scan"]
o, _ = A.answer("Утепление стен 150 мм недостаточно для зимы", OBJ)
check("позиция со скана передана в рассуждение (основания генератора)", seen and any(m == A.SCAN_MARK for _, m in seen[0]))
check("ссылка на скан в тексте — инженеру с причиной", o["route"] == "engineer" and o["internal"]["engineer_why"] == "данные проекта со скана — сверить с оригиналом")
check("в черновике инженеру позиция со скана с пометкой", any(b.get("mark") == A.SCAN_MARK for b in o["internal"]["draft_basis"]))
MODE[0] = "norm"; seen.clear()
o, _ = A.answer("Утепление стен 150 мм недостаточно для зимы", OBJ)
check("ответ без ссылки на скан — покупателю, как раньше", o["route"] == "client" and all(b.get("mark") != A.SCAN_MARK for b in o["basis"] if f"[{o['basis'].index(b) + 1}]" in o["reasoning"]))
A.analyze, A.select_basis, A.write, A.judge = orig
print(f"данные со скана: {ok}/{ok + len(fail)}", "" if not fail else f"ПРОВАЛ: {fail}")
sys.exit(1 if fail else 0)
