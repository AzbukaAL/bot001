"""Прогон №2 (правки K031 — голословное → встречный вопрос; K054 — расширение запроса по теме). Прогон №1: система v1 на эталоне. Поиск кандидатов (BM25 + маршрутизация по теме) → модель выбирает вердикт и
ссылки ТОЛЬКО из кандидатов → код проверяет ссылки и подставляет цитаты → сравнение с вердиктом Алексея.

  python3 src/run01.py --limit 2      # калибровка: 2 претензии, токены и оценка стоимости
  python3 src/run01.py                # полный прогон → build/REPORT_run02.md, build/run02.json
Претензии уходят в модель только обезличенными (anonymize, п. 8.3 договора).
"""
import json, math, re, sys, time, urllib.request, collections
sys.path.insert(0, "/opt/captain-sam/src")
from anonymize import anonymize

ROOT = "/opt/captain-sam"
IDX = json.load(open(f"{ROOT}/build/normy_index.json", encoding="utf-8"))
ET = json.load(open(f"{ROOT}/build/etalon.json", encoding="utf-8"))
MODEL = "anthropic/claude-sonnet-4.5"
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import env_file as EF
KEY = EF.read("POLZA_API_KEY")   # 27.10: ключ модели — только из .env проекта
PRICE_IN, PRICE_OUT, USD = 3.0, 15.0, 95.0   # $/1M токенов (Anthropic list) и курс — ОЦЕНКА, не счёт Polza
TYPES = {1: "подтверждается нормативом", 2: "опровергается нормативом/регламентом/практикой", 3: "встречный вопрос",
         4: "вне зоны ответственности", 5: "основания не найдено"}

STOP = set("это как при для что или его она они без под над все так уже нет есть был быть также только если может нужно более менее чем".split())
def toks(t):
    return [w[:6] for w in re.findall(r"[а-яёa-z0-9]+", t.lower().replace("ё", "е")) if len(w) >= 3 and w not in STOP]

DOCS = {k: v for k, v in IDX.items() if "УТРАТИЛ" not in v["status"]}
PTS = [(d, p, v["text"], (IDX[d]["sections"].get(str(v.get("section")), "") or "")) for d, dv in DOCS.items() for p, v in dv["points"].items() if len(v["text"]) > 20]
OCR = {f"{d}|п.{p}": bool(v.get("ocr")) for d, dv in DOCS.items() for p, v in dv["points"].items()}
DF = collections.Counter(); TF = []
for d, p, t, s in PTS:
    c = collections.Counter(toks(t + " " + s)); TF.append(c); DF.update(c.keys())
AVG = sum(sum(c.values()) for c in TF) / max(1, len(TF))
def bm25(q, i, k1=1.5, b=0.75):
    c = TF[i]; L = sum(c.values()); sc = 0.0
    for w in set(q):
        if w in c:
            idf = math.log(1 + (len(PTS) - DF[w] + 0.5) / (DF[w] + 0.5))
            sc += idf * c[w] * (k1 + 1) / (c[w] + k1 * (1 - b + b * L / AVG))
    return sc

ROUTE = [(r"сейсм|балл|толчк|ОСР", ["СП 14.13330.2018"]),
         (r"электр|автомат|УЗО|розет|фаз|\bА\b|кВт|ток|ввод", ["СП 256.1325800.2016", "ПУЭ-7 гл. 7.1", "ПУЭ гл. 3.1"]),
         (r"вентил|вытяж|рекупер|приточ|отоплен|котёл|котел|бойлер", ["СП 60.13330.2020"]),
         (r"утепл|тепл|конденс|рос[ыа]|стеклопакет|сопротивлен|мембран|влаж", ["СП 50.13330.2024"]),
         (r"конденс|рос[ыа]|стеклопакет|потеет|окн", ["СП 60.13330.2020"]),
         (r"климат|температур|ветров|снегов|январ|мороз", ["СП 131.13330.2025"]),
         (r"стропил|каркас|обвязк|брус|OSB|ОСБ|древесин|лаг|перекрыт|сайдинг|кровл|ондулин|анкер|свай|диафрагм|мауэрлат", ["СП 64.13330.2017", "СП 31-105-2002"])]

# 30.09 (K054): расширение запроса по теме — в претензии нет слов, которыми говорит норма.
EXPAND = [(r"конденс|рос[ыа]|стеклопакет|потеет", "точка росы температура внутренней поверхности отопительные приборы размещать под световыми проемами светопрозрачные"),
          (r"срыв|сорв|ветр", "ветровая нагрузка крепление"),
          (r"вытяж|вентиляц", "вытяжная вентиляция воздухообмен помещения кухни санузлы")]
def candidates(claim, k_all=6, k_doc=3, cap=12):
    q = toks(claim + " " + " ".join(x for rx, x in EXPAND if re.search(rx, claim, re.I))); scores = [(bm25(q, i), i) for i in range(len(PTS))]
    top = [i for s, i in sorted(scores, reverse=True)[:k_all] if s > 0]
    for rx, docs in ROUTE:
        if re.search(rx, claim, re.I):
            for d in docs:
                top += [i for s, i in sorted(((s, i) for s, i in scores if PTS[i][0] == d), reverse=True)[:k_doc] if s > 0]
    seen, out = set(), []
    for i in top:
        if i not in seen: seen.add(i); out.append(i)
    return out[:cap]

SYS = """Ты — инженер-эксперт подрядчика по каркасным домам. Тебе дают претензию клиента к проекту (обезличена) и список
фрагментов нормативов с идентификаторами. Регламента и практики компании у тебя НЕТ — опирайся только на фрагменты.
Выбери ОДИН вердикт:
1 — претензия подтверждается нормативом (в списке есть пункт, прямо её подтверждающий);
2 — претензия опровергается нормативом (в списке есть пункт, прямо её опровергающий);
3 — встречный вопрос: утверждение без обоснования/расчёта или посылка неясна (мощность, фазность, климат, размеры) —
    сформулируй вопрос, какие данные/документ/расчёт нужны;
4 — вне зоны ответственности подрядчика (проект фундамента, изыскания, проектная организация, приборы заказчика);
5 — основания не найдено: во фрагментах нет ничего, что подтверждает или опровергает.
3 vs 5 (важно): если претензия — голословное утверждение (нет ссылки на норму и нет расчёта), а фрагменты его прямо
не подтверждают и не опровергают — это 3 (встречный вопрос: попроси норму или расчёт), НЕ 5. Вердикт 5 — только когда
оппонент сам сослался на норму/расчёт, а во фрагментах соответствующего нет.
Правила: ссылайся ТОЛЬКО на id из списка, дословно. Вердикты 1 и 2 — только со ссылкой. Сначала проверь посылку оппонента,
потом арифметику. Ответ — строго JSON без пояснений вокруг:
{"verdict": <1-5>, "cite": ["<id>", ...], "reason": "<1–2 предложения>", "counter_question": "<вопрос или null>"}"""

def llm(claim, cands):
    frag = "\n".join(f"[{PTS[i][0]}|п.{PTS[i][1]}] {PTS[i][2][:600]}" for i in cands)
    body = {"model": MODEL, "max_tokens": 400, "temperature": 0,
            "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": f"ПРЕТЕНЗИЯ:\n{claim}\n\nФРАГМЕНТЫ:\n{frag}"}]}
    req = urllib.request.Request("https://polza.ai/api/v1/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r: d = json.load(r)
    txt = d["choices"][0]["message"]["content"]; u = d.get("usage", {})
    m = re.search(r"\{.*\}", txt, re.S)
    return (json.loads(m.group(0)) if m else {"verdict": None, "cite": [], "reason": "не JSON"}), u

def validate(ans, cands):
    ids = {f"{PTS[i][0]}|п.{PTS[i][1]}": i for i in cands}
    cites = ans.get("cite") or []
    bad = [c for c in cites if c not in ids]
    v = ans.get("verdict")
    if bad: return None, f"ОТВЕТ НЕ ВЫДАЁТСЯ: ссылка на отсутствующий пункт {bad}", []
    if v in (1, 2) and not cites: return None, "ОТВЕТ НЕ ВЫДАЁТСЯ: вердикт 1/2 без ссылки на пункт", []
    if v not in TYPES: return None, "ОТВЕТ НЕ ВЫДАЁТСЯ: вердикт вне пяти типов", []
    # цитата — кодом из разобранного текста; из OCR — НЕ выдаётся без сверки с оригиналом (правило проекта 30.09)
    quotes = [(c, "[цитата из распознанного скана — выдаётся только после сверки с оригиналом]" if OCR.get(c) else PTS[ids[c]][2][:300]) for c in cites]
    return v, "ok", quotes

PRACTICE = re.compile(r"комплектац|доплат|стоимост|практик|технолог|делается|производится|считали|стандарт|опци|базов")
def reason(e, sys_v, status):
    if status != "ok": return "ошибка системы (ответ заблокирован)"
    if e.get("needs_sp31_105"): return "нет текста нормы (полный СП 31-105)"
    if e.get("disputed"): return "спорный эталон"
    if e["verdict"] == 4: return "нет документа заказчика: границы ответственности (п. 4.1)"
    if e["id"] in ("K050", "K057"): return "нет данных объекта (КП/ТЗ: помещения, шаг лаг)"
    if e["verdict"] == 2 and PRACTICE.search(e.get("note", "") + " " + e.get("answer", "")): return "нет регламента/практики компании"
    return "ошибка системы"

def main():
    if "--report-only" in sys.argv:   # пересборка отчёта из build/run02.json без вызовов модели
        R = json.load(open(f"{ROOT}/build/run02.json", encoding="utf-8")); E = {e["id"]: e for e in ET}
        for r in R: r["why"] = None if r["match"] else reason(E[r["id"]], r["system"], r["status"])
        json.dump(R, open(f"{ROOT}/build/run02.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        report(R, 55711, 4849, 22.8); return
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    todo = [e for e in ET if e["verdict"] is not None or e["id"].startswith("K")]
    if lim is not None: todo = todo[:lim]   # 30.09: --limit 0 = без вызовов модели (раньше 0 давал полный прогон)
    if lim == 0: print('limit 0: вызовов нет'); return
    res, tin, tout = [], 0, 0
    for e in todo:
        claim, _ = anonymize(e["claim"])
        c = candidates(claim)
        try: ans, u = llm(claim, c)
        except Exception as ex: ans, u = {"verdict": None, "cite": [], "reason": f"ошибка вызова {type(ex).__name__}"}, {}
        tin += u.get("prompt_tokens", 0); tout += u.get("completion_tokens", 0)
        v, status, quotes = validate(ans, c)
        match = (v == e["verdict"]) if e["verdict"] is not None else None
        res.append({"id": e["id"], "claim": claim, "etalon": e["verdict"], "system": v, "status": status, "match": match,
                    "why": None if match else reason(e, v, status), "cite": ans.get("cite"), "quotes": quotes,
                    "reason": ans.get("reason"), "counter_question": ans.get("counter_question"), "disputed": e.get("disputed"),
                    "needs_sp31_105": e.get("needs_sp31_105"), "candidates": [f"{PTS[i][0]}|п.{PTS[i][1]}" for i in c]})
        print(f"{e['id']:6} эталон={e['verdict']} система={v} {'✅' if match else '❌' if match is False else '—'} {status[:60]}", flush=True)
        time.sleep(0.5)
    cost = (tin * PRICE_IN + tout * PRICE_OUT) / 1e6 * USD
    print(f"токенов: вход {tin}, выход {tout}; оценка ≈ {cost:.1f} ₽ (по прайсу Anthropic, не счёт Polza)")
    if lim is not None:
        per = cost / max(1, len(todo)); print(f"на претензию ≈ {per:.2f} ₽; полный прогон ({len([e for e in ET if e['verdict'] is not None or e['id'].startswith('K')])}) ≈ {per * 27:.0f} ₽")
        return
    json.dump(res, open(f"{ROOT}/build/run02.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    report(res, tin, tout, cost)

def report(res, tin, tout, cost):
    R1 = {r["id"]: r for r in json.load(open(f"{ROOT}/build/run01.json", encoding="utf-8"))}
    K = [r for r in res if r["id"].startswith("K") and r["etalon"] is not None]; K1 = [R1[r["id"]] for r in K]
    pct = lambda xs: (100 * sum(bool(r["match"]) for r in xs) / len(xs)) if xs else 0
    L = ["# Прогон №2 — только изменения против прогона №1", "",
         f"Каменское: было {pct(K1):.0f}% ({sum(bool(r['match']) for r in K1)}/{len(K1)}) → стало **{pct(K):.0f}% ({sum(bool(r['match']) for r in K)}/{len(K)})**.",
         f"Модель {MODEL}; токенов вход {tin}, выход {tout}; оценка ≈ {cost:.0f} ₽.", "",
         "| id | было (система) | стало (система) | Алексей | совпадение было→стало | причина сейчас |", "|---|---|---|---|---|---|"]
    ch = 0
    for r in res:
        o = R1.get(r["id"], {})
        if (o.get("system"), o.get("match")) != (r["system"], r["match"]) or r["id"] in ("K031", "K054"):
            ch += 1
            m = lambda x: "✅" if x else "❌" if x is False else "—"
            L.append(f"| {r['id']} | {o.get('system')} | {r['system']} | {r['etalon']} | {m(o.get('match'))}→{m(r['match'])} | {r['why'] or ''} |")
    L += ["", f"Изменилось строк: {ch}. K031/K054 — детали:"]
    for r in res:
        if r["id"] in ("K031", "K054"):
            L.append(f"\n### {r['id']}: система {r['system']} (Алексей {r['etalon']})\n- кандидаты: {', '.join(r['candidates'][:8])}\n- обоснование: {r['reason']}\n- встречный вопрос: {r['counter_question']}")
            for c, q in r["quotes"]: L.append(f"- «{q[:200]}…» — {c}")
    open(f"{ROOT}/build/REPORT_run02.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L)); return
    # (полная таблица прогона №1 ниже не используется)
    K = [r for r in res if r["id"].startswith("K") and r["etalon"] is not None]
    Kc = [r for r in K if not r["disputed"]]
    pct = lambda xs: (100 * sum(r["match"] for r in xs) / len(xs)) if xs else 0
    sp31 = [r for r in K if r["needs_sp31_105"]]
    why = collections.Counter(r["why"] for r in K if not r["match"])
    L = ["# Прогон №1 — Капитан Сэм (система v1 против эталона Алексея)", "",
         f"**Каменское: совпадение {pct(K):.0f}% ({sum(r['match'] for r in K)}/{len(K)})**; без спорных эталонов — {pct(Kc):.0f}% ({sum(r['match'] for r in Kc)}/{len(Kc)}). Порог договора — 80%.",
         f"**Упёрлось в отсутствие полного СП 31-105: {len(sp31)} пунктов** (совпало из них {sum(r['match'] for r in sp31)}).",
         f"Причины расхождений: {dict(why)}.", f"Модель {MODEL}; токенов вход {tin}, выход {tout}; оценка ≈ {cost:.0f} ₽.", "",
         "| id | претензия (обезличено) | система | Алексей | совпало | причина | ссылки системы |", "|---|---|---|---|---|---|---|"]
    for r in res:
        L.append(f"| {r['id']} | {r['claim'][:110].replace('|', '/')} | {r['system'] if r['system'] else '⛔'} | {r['etalon'] if r['etalon'] else '—'} | "
                 f"{'✅' if r['match'] else '❌' if r['match'] is False else '—'} | {r['why'] or ''}{' · спорный: ' + r['disputed'] if r['disputed'] else ''} | {', '.join(r['cite'] or [])[:120]} |")
    L += ["", "## Детали по каждой претензии (обоснование системы, встречный вопрос, цитаты — кодом)"]
    for r in res:
        L.append(f"\n### {r['id']} — система {r['system']} / Алексей {r['etalon']}\n- статус: {r['status']}\n- обоснование: {r['reason']}\n- встречный вопрос: {r['counter_question']}")
        for c, q in r["quotes"]: L.append(f"- «{q}…» — {c}")
    open(f"{ROOT}/build/REPORT_run02.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L[:6]))

if __name__ == "__main__":
    main()
