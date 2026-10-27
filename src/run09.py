"""Прогон №9 (08.10.2026) против эталона v2 (разметка инженера). Промпт и пороги — как в №8: исходник src/run08.py исполняется
как есть, подменяются только (1) индекс норм → build/normy_index_v2.json (полные СП 31-105-2002 и СП 24.13330.2021),
(2) эталон → build/etalon_v2.json, (3) маршрут поиска: «свай|ростверк|фундамент» → СП 24 (иначе новый документ почти не попадает
в кандидаты). Больше ничего.
  №9а: python3 src/run09.py            → build/run09a.json, build/REPORT_run09a.md
  №9б: python3 src/run09.py --objects  → только в ветке wip/* (данные объекта = правка промпта)
Регрессия: прежний набор (K031, K054, P9–10) — вердикт системы не хуже №8 по эталону v1 (так он определялся); отдельно — v2.
"""
import os
import collections, json, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBJECTS = "--objects" in sys.argv
TAG = "09b" if OBJECTS else "09a"
if OBJECTS: sys.exit("№9б (данные объекта) — только в ветке wip/run09b-objects: это правка промпта")

src = open(f"{ROOT}/src/run08.py", encoding="utf-8").read()
for a, b in [('build/normy_index.json', 'build/normy_index_v2.json'), ('build/etalon.json', 'build/etalon_v2.json')]:
    assert src.count(a) == 1, a; src = src.replace(a, b)
assert src.count("ROUTE = [") == 1
src = src.replace("ROUTE = [", 'ROUTE = [(r"свай|ростверк|фундамент", ["СП 24.13330.2021"]),\n         ', 1)
R8 = {"__name__": "run08_v2"}
exec(compile(src, "run08.py (индекс v2)", "exec"), R8)

ET2 = {e["id"]: e for e in R8["ET"]}
ET1 = {e["id"]: e for e in json.load(open(f"{ROOT}/build/etalon.json", encoding="utf-8"))}
RUN8 = {r["id"]: r for r in json.load(open(f"{ROOT}/build/run08.json", encoding="utf-8"))}
IDS = [r["id"] for r in RUN8.values()]          # те же 24 пары, что в №8 (для сравнимости и регрессии)
REGRESSION = ["K031", "K054", "P9–10"]

def main():
    res, tin, tout = [], 0, 0
    for i in IDS:
        claim, _ = R8["anonymize"](ET1[i]["claim"])
        c = R8["candidates"](claim); rc = R8["reg_candidates"](claim)
        try: ans, u = R8["llm"](claim, c, rc)
        except Exception as ex: ans, u = {"verdict": None, "cite": [], "reason": f"ошибка вызова {type(ex).__name__}"}, {}
        tin += u.get("prompt_tokens", 0); tout += u.get("completion_tokens", 0)
        v, status, quotes = R8["validate"](ans, c, rc)
        e2 = ET2.get(i, {}); v2 = e2.get("verdict")
        res.append({"id": i, "system": v, "status": status, "etalon_v2": v2, "etalon_v1": ET1[i]["verdict"], "run08": RUN8[i]["system"],
                    "match_v2": (v == v2) if v2 is not None else None, "match_v1": (v == ET1[i]["verdict"]) if ET1[i]["verdict"] is not None else None,
                    "fact_from_etalon": e2.get("fact_from_etalon", False), "direct": ans.get("direct"), "evidence": ans.get("evidence"),
                    "cite": ans.get("cite"), "reason": ans.get("reason"), "counter_question": ans.get("counter_question"),
                    "candidates": [f"{R8['PTS'][j][0]}|п.{R8['PTS'][j][1]}" for j in c] + list(rc),
                    "new_docs_in_candidates": [x for x in [f"{R8['PTS'][j][0]}|п.{R8['PTS'][j][1]}" for j in c] if x.startswith(("СП 31-105", "СП 24.13330"))]})
        print(f"{i:6} v2={v2} система={v} (№8: {RUN8[i]['system']}) {status[:50]}", flush=True)
        time.sleep(0.5)
    cost = (tin * R8["PRICE_IN"] + tout * R8["PRICE_OUT"]) / 1e6 * R8["USD"]
    json.dump(res, open(f"{ROOT}/build/run{TAG}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    report(res, cost)

def pct(rows, key):
    rr = [r for r in rows if r[key] is not None]; return sum(r[key] for r in rr), len(rr)

def report(res, cost):
    K = [r for r in res if r["id"].startswith("K")]
    m2, n2 = pct(K, "match_v2"); m1, n1 = pct(K, "match_v1")
    K8 = [{"match_v2": (RUN8[r["id"]]["system"] == r["etalon_v2"]) if r["etalon_v2"] is not None else None} for r in K]
    m8, n8 = pct(K8, "match_v2")
    reg = {i: next(r for r in res if r["id"] == i) for i in REGRESSION}
    reg_ok = all((r["system"] == ET1[i]["verdict"]) or (RUN8[i]["system"] != ET1[i]["verdict"]) for i, r in reg.items())
    L = [f"# Прогон №{TAG[1:]} — эталон v2 (инженер), индекс норм v2" + (" + данные объекта" if OBJECTS else ""), "",
         f"Каменское против **эталона v2**: №8 — {m8}/{n8}, №{TAG[1:]} — **{m2}/{n2}** ({100 * m2 // max(1, n2)}%).",
         f"Для сравнения — против эталона v1 (продажи): {m1}/{n1}.",
         f"Регрессия (K031, K054, P9–10; как определялась — по v1, не хуже №8): " + ("✅ удержана" if reg_ok else "❌ ПОТЕРЯНА") + " — " +
         ", ".join(f"{i}: {r['system']} (№8 {RUN8[i]['system']}, v1 {ET1[i]['verdict']}, v2 {r['etalon_v2']})" for i, r in reg.items()),
         f"Оценка ≈ {cost:.0f} ₽.", ""]
    if OBJECTS:
        F = [r for r in K if r["fact_from_etalon"]]; NF = [r for r in K if not r["fact_from_etalon"]]
        a, b = pct(F, "match_v2"); c_, d = pct(NF, "match_v2")
        L += [f"**Факт из эталона** (факт объекта взят из ответа инженера на эту же претензию — совпадение завышено): {a}/{b} — "
              + ", ".join(r["id"] for r in F) + f". Без них: **{c_}/{d}**.", ""]
    L += ["| id | v2 | система | №8 | совп. v2 | новые СП в кандидатах | прямой фрагмент |", "|---|---|---|---|---|---|---|"]
    for r in res:
        L.append(f"| {r['id']}{' *' if r['fact_from_etalon'] and OBJECTS else ''} | {r['etalon_v2']} | {r['system']} | {r['run08']} | "
                 f"{'✅' if r['match_v2'] else '❌' if r['match_v2'] is False else '—'} | {len(r['new_docs_in_candidates'])} | {r['direct'] or '—'} |")
    open(f"{ROOT}/build/REPORT_run{TAG}.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L[:8]))

if __name__ == "__main__":
    main()
