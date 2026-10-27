"""Исключения в пункте нормы (21.10.2026, решение Вадима, кейс R02 «слив воды»): цитата пункта — целиком или с исключением;
модели вердикта — пункт без среза 600 и данные проекта. Без вызовов модели.  python3 src/test_norm_exceptions.py"""
import io, json, os, re, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import answer as A, run08 as R

ok = 0; fail = []
def check(name, cond):
    global ok
    if cond: ok += 1
    else: fail.append(name)

REF = "СП 60.13330.2020|п.6.2.16"
q = A.norm_quote(REF, "В системах отопления следует предусматривать устройства для удаления воздуха и их опорожнения.")
check("6.2.16: цитата целиком, с исключением про продувку", "вместо спуска воды продувку" in q and q.startswith("В системах отопления"))
check("6.2.16: колонтитул «23 СП 60…» вычищен", "23 СП 60" not in q)
longs = [(f"{p[0]}|п.{p[1]}", p[2]) for p in R.PTS if len(p[2]) > A.NORM_QUOTE_MAX and A.EXC.search(p[2][700:])]
ref2, txt2 = longs[0]
first = A.sentences(txt2)[0]
q2 = A.norm_quote(ref2, first)
check("длинный пункт: выбранная часть + предложения с исключением", q2.startswith(first) and " … " in q2 and A.EXC.search(q2[len(first):]))
check("длинный пункт: не весь пункт", len(q2) < len(txt2))
V = next(iter(A.VERIFIED))
check("вручную сверенный пункт не расширяется (select_basis пропускает VERIFIED)", "ref not in VERIFIED" in open(A.__file__, encoding="utf-8").read())
check("СК не трогаем", "not ref.startswith(\"СК-\")" in open(A.__file__, encoding="utf-8").read())

# модель вердикта: пункт целиком и данные проекта
bodies = []
class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()
def fake(req, *a, **kw):
    bodies.append(json.loads(req.data))
    return Resp(json.dumps({"choices": [{"message": {"content": '{"step": "в", "direct": null, "evidence": null, "verdict": 3, "cite": [], "reason": "x", "counter_question": "?"}'}}],
                            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost_rub": 0}}).encode())
real = urllib.request.urlopen; urllib.request.urlopen = fake; A.CALLS_LOG = "/dev/null"
long_i = max(range(len(R.PTS)), key=lambda i: len(R.PTS[i][2]) if R.PTS[i][0] == "СП 60.13330.2020" and len(R.PTS[i][2]) <= R.NORM_VERDICT_MAX else 0)
R._llm_once("почему не предусмотрен слив воды", [long_i, R.PTS.index(next(p for p in R.PTS if f"{p[0]}|п.{p[1]}" == REF))])
u = bodies[-1]["messages"][1]["content"]
check("вердикт: длинный пункт не срезан на 600", len(R.PTS[long_i][2]) > 600 and R.PTS[long_i][2][-60:] in u)
check("вердикт: в системном промпте правило исключений", "ИСКЛЮЧЕНИЯ В ПУНКТЕ НОРМЫ" in bodies[-1]["messages"][0]["content"])
OBJ = {"label": "Данные Вашего проекта", "items": [{"id": "X1", "позиция": "Отопление",
       "описание": "Система отопления горизонтальная, трубы полимерные, радиаторы алюминиевые", "источник_метка": "опросный лист от 21.10.2026"}]}
bodies.clear(); A.analyze("почему не предусмотрен слив воды с системы отопления?", OBJ)
u = bodies[0]["messages"][1]["content"]
check("вердикт: данные проекта переданы блоком", "ДАННЫЕ ПРОЕКТА" in u and "горизонтальная, трубы полимерные" in u)
bodies.clear(); a = A.analyze("почему не предусмотрен слив воды с системы отопления?")
check("вердикт без данных проекта — блока нет, претензия как была", "ДАННЫЕ ПРОЕКТА" not in bodies[0]["messages"][1]["content"] and a["claim"].startswith("почему"))
urllib.request.urlopen = real
check("генератор: правило исключения в промпте при основании-норме с исключением", "EXC_WRITE_RULE if any(EXC.search" in open(A.__file__, encoding="utf-8").read())
print(f"исключения в нормах: {ok}/{ok + len(fail)}", "" if not fail else f"ПРОВАЛ: {fail}")
sys.exit(1 if fail else 0)
