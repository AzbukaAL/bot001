"""Тон и ирония — настройка Заказчика (21.10.2026, Прил. 1, п. 2.5): команда в боте только для белого списка; по умолчанию —
стиль как был; смена уровня меняет ТОЛЬКО промпт генератора текста — вердикт, основания, цитаты те же. Модель подменена.
python3 src/test_tone_setting.py"""
import hashlib, io, json, os, sys, tempfile, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import answer as A, bot_max as B

ok = 0; fail = []
def check(name, cond):
    global ok
    if cond: ok += 1
    else: fail.append(name)
tmp = tempfile.mkdtemp(); A.SETTINGS = f"{tmp}/settings.json"; A.CALLS_LOG = "/dev/null"
B.notify = lambda t: None
check("по умолчанию — стиль как был, блок пустой", A.style() == A.STYLE_DEFAULT and A.style_block() == "")
STAFF, STRANGER = 424242, 999
check("белый список — из .env (SETTINGS_USERS), множество", isinstance(B.SETTINGS_USERS, set))
B.SETTINGS_USERS = {STAFF, 424243}
r = B.settings_cmd(STRANGER, "/ирония 2")
check("не из списка — отказ, настройка не меняется", r.startswith("Менять тон и иронию могут только") and A.style()["irony"] == 0)
check("/настройки — видно всем", B.settings_cmd(STRANGER, "/настройки").startswith("Сейчас: ирония 0 из 2"))
check("неверный аргумент — подсказка", B.settings_cmd(STAFF, "/ирония 5").startswith("Не понял"))

# запросы к модели при иронии 0 и 2: вердикт и выбор основания — те же, генератор — плюс блок «СТИЛЬ»
class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()
calls = []
FIX = {"verdict": '{"step": "а", "direct": null, "evidence": null, "verdict": 3, "cite": [], "reason": "нет расчёта", "counter_question": "Какой расчёт?"}',
       "select": '{"chosen": []}', "write": '{"conclusion": "Для ответа нужны данные", "short": "Нужен расчёт.", "reasoning": "Нужен расчёт.", "action": null, "clarify": null}',
       "judge": '{"stance": "за покупателя", "addresses": true, "formal": false}'}
def fake(req, *a, **kw):
    b = json.loads(req.data); sysmsg = b["messages"][0]["content"]
    step = "verdict" if sysmsg.startswith(A.R8.SYS[:200]) else "select" if sysmsg == A.SELECT_SYS else "write" if sysmsg == A.WRITE_SYS else "judge"
    calls.append((step, hashlib.md5(req.data).hexdigest(), b["messages"][1]["content"]))
    return Resp(json.dumps({"choices": [{"message": {"content": FIX[step]}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost_rub": 0}}).encode())
real = urllib.request.urlopen; urllib.request.urlopen = fake
CLAIM = "Автомат 25 А на вводе мал, при 15 кВт на трёх фазах нужен 32 А"
o0, _ = A.answer(CLAIM); c0 = list(calls); calls.clear()
check("команда сотрудника из списка меняет настройку", B.settings_cmd(STAFF, "/ирония 2").startswith("Готово.") and B.settings_cmd(STAFF, "/тон мягкий").startswith("Готово.")
      and A.style() == {"irony": 2, "tone": "мягкий"} and json.load(open(A.SETTINGS))["updated_by"] == STAFF)
o2, _ = A.answer(CLAIM); c2 = list(calls)
md = lambda cs, st: [m for s, m, _ in cs if s == st]
check("вердикт: запросы к модели те же", md(c0, "verdict") == md(c2, "verdict") and md(c0, "verdict"))
check("выбор основания: запросы те же", md(c0, "select") == md(c2, "select"))
w0 = [u for s, _, u in c0 if s == "write"]; w2 = [u for s, _, u in c2 if s == "write"]
check("генератор: промпт = прежний + только блок «СТИЛЬ»", w0 and all(b.startswith(a) and "СТИЛЬ (настройка Заказчика)" in b[len(a):] and "ЗАМЕТНАЯ ирония" in b
      and "Тон мягкий" in b for a, b in zip(w0, w2)))
check("вердикт, основания, цитаты, расчёт — те же", o0["internal"]["verdict"] == o2["internal"]["verdict"] and o0["basis"] == o2["basis"] and o0["calc"] == o2["calc"])
check("в трассе — стиль ответа", o0["trace"]["style"] == {"irony": 0, "tone": "деловой"} and o2["trace"]["style"] == {"irony": 2, "tone": "мягкий"})
check("проверки фактов не зависят от настройки", "style" not in open(A.__file__, encoding="utf-8").read().split("def _check_facts", 1)[1].split("\ndef ", 1)[0])
B.settings_cmd(STAFF, "/ирония 0"); B.settings_cmd(STAFF, "/тон деловой")
check("возврат к 0 и «деловой» — снова прежний промпт", A.style_block() == "")
urllib.request.urlopen = real
print(f"тон и ирония: {ok}/{ok + len(fail)}", "" if not fail else f"ПРОВАЛ: {fail}")
sys.exit(1 if fail else 0)
