"""wip/verdict-rules (27.10.2026, решение Вадима): (1) K030 — части цитаты-доказательства, найденные дословно, заменяются
предложениями источника, порог — слово, отклоняется только часть, которой в источнике нет; для норм и регламента одинаково;
(2) K041 — материал-предмет замечания (первый названный в группе) и «основание о другом материале» на шаге вердикта:
такие фрагменты исключаются, вердикт запрашивается заново. Модель подменена, сети нет.   python3 src/test_verdict_rules.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run08 as R8

ok = 0; fail = []
def check(name, cond):
    global ok
    if cond: ok += 1
    else: fail.append(name)

SRC = ("Для каждого вида покрытия соблюдаются предусмотренные для него минимальные уклоны, требования к основанию, шагу обрешетки, "
       "величине нахлестов, способу и количеству креплений. Листы крепят по верху волны. Иное не допускается.")
# (1) предложения источника
ev = R8.sentences_with(SRC, ["соблюдаются", "требования", "к основанию"])
check("части одного предложения → это предложение целиком", ev == SRC.split(". ")[0] + ".")
ev2 = R8.sentences_with(SRC, ["соблюдаются", "по верху волны"])
check("части из двух соседних предложений → оба подряд, третьего нет", ev2.startswith("Для каждого") and ev2.endswith("Листы крепят по верху волны.") and "Иное" not in ev2)
ev3 = R8.sentences_with(SRC, ["соблюдаются", "иное не допускается"])
check("части из несоседних предложений → через « … », среднего нет", ev3.startswith("Для каждого") and " … Иное не допускается." in ev3 and "по верху волны" not in ev3)
check("часть с начальным предлогом («к шагу обрешетки») находится без него", "шагу обрешетки" in R8.sentences_with(SRC, ["к шагу обрешетки"]))
check("части нет в источнике → ничего", R8.sentences_with(SRC, ["гвозди в нижнюю волну"]) == "")

# (1) цикл вердикта с подменённой моделью: обрывки «…» короче 20 символов проходят, evidence — предложение
cands = [0, 1]; d0 = f"{R8.PTS[0][0]}|п.{R8.PTS[0][1]}"
real_src = R8.PTS[0][2]; sent0 = R8.sentences_with(real_src, [real_src.lower().split()[0]])
words = [w for w in real_src.split() if len(w) >= 6][:3]
calls = []
def fake(answers):
    it = iter(answers)
    def f(claim, c, rc=(), extra=""):
        calls.append({"cands": list(c), "rcands": list(rc), "extra": extra}); return next(it), {}
    return f
R8._llm_once = fake([{"verdict": 2, "direct": d0, "evidence": " … ".join(words), "cite": [d0], "reason": "x"}])
ans, _ = R8.llm("претензия", cands, [])
check("обрывки по слову, найденные дословно → вердикт 2 принят с первой попытки", ans.get("verdict") == 2 and ans.get("attempts") == 1 and len(calls) == 1)
check("evidence заменён предложениями источника", all(w.lower() in ans["evidence"].lower() for w in words) and ans["evidence"] != " … ".join(words))
v, st, _ = R8.validate(ans, cands, [])
check("validate пропускает", v == 2 and st == "ok")
calls.clear()
R8._llm_once = fake([{"verdict": 2, "direct": d0, "evidence": words[0] + " … этого в источнике нет никогда", "cite": [d0]}] * 2)
ans, _ = R8.llm("претензия", cands, [])
check("часть, которой нет в источнике → две попытки, блок как раньше", len(calls) == 2 and ans.get("evidence_fail") and R8.validate(ans, cands, [])[0] is None)
check("во второй попытке — напоминание про дословную цитату", "дословной цитатой" in calls[1]["extra"])
# регламент — тем же путём
rid = next(iter(R8.REG)); rsrc = R8.REG[rid]["text"]; rw = [w for w in rsrc.split() if len(w) >= 6][:2]
calls.clear(); R8._llm_once = fake([{"verdict": 2, "direct": rid, "evidence": " … ".join(rw), "cite": [rid]}])
ans, _ = R8.llm("претензия", cands, [rid])
check("регламент: обрывки → предложение, вердикт принят", ans.get("verdict") == 2 and all(w.lower() in ans["evidence"].lower() for w in rw))

# (2) материал-предмет
K041 = "Виниловый сайдинг в условиях сильных ветров и солнца. На ветру может отрываться от обрешётки, в отличие от имитации бруса."
check("предмет — первый названный материал группы", R8.subject_materials(K041)["фасад"] == {"сайдинг"})
check("без материалов — пусто", R8.subject_materials("Крепится гвоздями")["фасад"] == set() and R8.subject_materials("Крепится гвоздями")["кровля"] == set())
check("другой материал: имитация бруса вместо сайдинга", R8.other_material(R8.subject_materials(K041), "Имитация бруса обрабатывается защитным составом") == "деревянная облицовка вместо сайдинг")
check("тот же материал — не конфликт", R8.other_material(R8.subject_materials(K041), "Сайдинг крепят к обрешётке") is None)
check("материалы проекта расширяют «есть»", R8.other_material({"фасад": {"сайдинг", "деревянная облицовка"}}, "Имитация бруса …") is None)
# на шаге вердикта: модель цитирует фрагмент о деревянной облицовке → фрагмент исключён, повторный вызов без него
wid = next((r for r, v in R8.REG.items() if R8.MAT_RX["фасад"]["деревянная облицовка"].search(v["text"]) and not R8.MAT_RX["фасад"]["сайдинг"].search(v["text"])), None)
check("в регламенте есть раздел про деревянную облицовку (для теста)", wid is not None)
if wid is not None:
    wtxt = R8.REG[wid]["text"]; wwords = [w for w in wtxt.split() if len(w) >= 6][:2]
    calls.clear()
    R8._llm_once = fake([{"verdict": 2, "direct": wid, "evidence": " … ".join(wwords), "cite": [wid]},
                         {"verdict": 3, "direct": None, "evidence": None, "cite": [], "counter_question": "какой производитель?"}])
    ans, _ = R8.llm(K041, [0], [wid])
    check("первый ответ о другом материале → второй вызов", len(calls) == 2)
    check("во втором вызове фрагмент о другом материале исключён", wid not in calls[1]["rcands"] and 0 in calls[1]["cands"])
    check("напоминание называет материалы", "деревянная облицовка вместо сайдинг" in calls[1]["extra"])
    check("итог — ответ второй попытки (3), прежнее правило 3/5 не тронуто", ans.get("verdict") == 3 and ans.get("attempts") == 2)
    calls.clear()
    R8._llm_once = fake([{"verdict": 2, "direct": wid, "evidence": " … ".join(wwords), "cite": [wid]}] * 2)
    ans, _ = R8.llm(K041, [0], [wid])
    v, st, _ = R8.validate(ans, [0], [])
    check("снова тот же фрагмент → не выдаётся, причина названа", v is None and ("другом материале" in st or "отсутствующий пункт" in st))
    calls.clear()
    R8._llm_once = fake([{"verdict": 2, "direct": wid, "evidence": " … ".join(wwords), "cite": [wid]}])
    ans, _ = R8.llm("Крепится гвоздями в верхнюю часть волны", [0], [wid])
    check("без материала-предмета в замечании проверка молчит", len(calls) == 1 and ans.get("verdict") == 2)
# answer.material_conflict — теперь по предмету
import answer as A
check("answer.material_conflict: сайдинг — предмет, имитация бруса в замечании — сравнение", A.material_conflict(K041, ["Имитация бруса или блок-хаус обрабатываются системой защитных материалов"], None) == "основание о другом материале: деревянная облицовка вместо сайдинг")

print(f"правила вердикта (K030, K041): {ok}/{ok + len(fail)}" + (f"\nПРОВАЛ: {fail}" if fail else ""))
sys.exit(1 if fail else 0)
