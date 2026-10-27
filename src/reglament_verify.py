"""Пункт 2+3: статусы документов из регламента и сверка ссылок регламента на пункты («пункт существует и говорит то,
что утверждается»). Выход: build/REGLAMENT_CHECK.md. Демо для заказчика — формулировки нейтральные."""
import json, re, sys, urllib.request
ROOT = "/opt/captain-sam"
IDX = json.load(open(f"{ROOT}/build/normy_index.json", encoding="utf-8"))
CL = json.load(open(f"{ROOT}/build/reglament_claims.json", encoding="utf-8"))
REFS = json.load(open(f"{ROOT}/build/reglament_refs.json", encoding="utf-8"))
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import env_file as EF
KEY = EF.read("POLZA_API_KEY")   # 27.10: ключ модели — только из .env проекта

# Статусы — по проверке 30.09.2026 (Росстандарт protect.gost.ru + docs.cntd.ru; реестр ФЦС не использовался).
STATUS = {
 "СП 31-105": ("не удалось проверить", "в реестре СП Росстандарта нет; документ 2002 г., одобрен Госстроем, рекомендательный"),
 "СП 64.13330": ("действует, актуальна", "2017 с изм. 1–4"), "СП 50.13330": ("действует, актуальна", "2024; ред. 2012 заменена"),
 "СП 17.13330": ("действует, актуальна", "2017 с изм. 1–5"), "СП 20.13330": ("действует, актуальна", "2016 с изм. 1–6"),
 "ГОСТ 23166": ("действует, актуальна", "ГОСТ 23166-2024 (заменил -2021)"), "СП 28.13330": ("действует, актуальна", "2017 с изм. 1–4"),
 "СП 55.13330": ("действует, актуальна", "2016 с изм. 1–2"), "СП 71.13330": ("действует, актуальна", "2017 с изм. 1–4"),
 "СП 402.1325800": ("действует, актуальна", "2018 с изм. 1"), "СП 24.13330": ("действует, актуальна", "2021 с изм. 1–2"),
 "ГОСТ 30971": ("действует, актуальна", "2012; частичная замена отменена в 2022"),
 "ГОСТ 33124": ("действует до 01.12.2026", "с 01.12.2026 заменяется ГОСТ 33124-2026"), "ГОСТ Р 58955": ("действует, актуальна", "2020"),
 "СП 352.1325800": ("действует, актуальна", "2017 с изм. 1–2"), "СП 29.13330": ("год не указан — действует СП 29.13330.2011", "2011 с изм. 1–4"),
 "СП 22.13330": ("действует, актуальна", "2016 с изм. 1–5"), "ГОСТ 9.602": ("год не указан — действует ГОСТ 9.602-2016", ""),
 "СП 70.13330": ("действует, не заменён", "2012 с изм. 1, 3–8"), "ГОСТ 1759.0": ("год не указан — действует ГОСТ 1759.0-87", ""),
 "ГОСТ 35290": ("действует, актуальна (документ существует)", "2025, введён 01.06.2026"), "ГОСТ 25898": ("действует, актуальна", "2020"),
 "ГОСТ 31899-2": ("действует, актуальна", "2011"), "ГОСТ 8486": ("год не указан — действует ГОСТ 8486-86", ""),
 "ГОСТ 30674": ("действует, актуальна", "2023"), "ГОСТ 24866": ("действует, актуальна", "2014 с изм. 1–2"),
 "ГОСТ 31173": ("действует, актуальна", "2016"), "СП 30.13330": ("действует, актуальна", "2020 с изм. 1–5"),
 "СП 32.13330": ("действует, актуальна", "2018 с изм. 1–5"),
}
def base(d):   # «СП 17.13330.2017» → «СП 17.13330»; «ГОСТ 23166-2024» → «ГОСТ 23166»
    d = re.sub(r"\.(19|20)\d\d$", "", d); d = re.sub(r"-(19|20)\d\d$", "", d); return d
def have(b):
    full = [k for k, v in IDX.items() if base(k) == b or k.startswith(b + "-")]
    full = [k for k in full if " изм. " not in k]
    if not full: return "нет", None
    k = full[0]; return ("целиком" if IDX[k]["kind"] == "full" else "фрагмент") + (" (OCR)" if any(p.get("ocr") for p in IDX[k]["points"].values()) else ""), k

L = ["# Регламент заказчика: документы и ссылки на пункты (30.09.2026)", "",
     "## 1. Упомянутые документы — статус и наличие у нас", "", "| Документ (как в регламенте) | Упоминаний | Статус | Действующая редакция | У нас |", "|---|---|---|---|---|"]
seen = {}
for d, r in sorted(REFS.items(), key=lambda x: -x[1]["count"]):
    if not re.search(r"\d", d): continue
    b = base(d); seen.setdefault(b, []).append((d, r["count"]))
for b, lst in seen.items():
    st, ed = STATUS.get(b, ("—", ""))
    L.append(f"| {', '.join(x for x, _ in lst)} | {sum(n for _, n in lst)} | {st} | {ed} | {have(b)[0]} |")

def llm(claim, doc, pt, text):
    body = {"model": "anthropic/claude-sonnet-4.5", "max_tokens": 300, "temperature": 0, "messages": [
        {"role": "system", "content": "Сверь утверждение из регламента строительной компании с текстом пункта норматива (текст может быть распознан OCR с опечатками). "
         "Ответ строго JSON: {\"verdict\": \"подтверждается|частично|не подтверждается|пункт о другом\", \"why\": \"1–2 предложения\"}."},
        {"role": "user", "content": f"УТВЕРЖДЕНИЕ: {claim}\n\nДОКУМЕНТ: {doc}, {pt}\nТЕКСТ ПУНКТА:\n{text[:3500]}"}]}
    req = urllib.request.Request("https://polza.ai/api/v1/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r: t = json.load(r)["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", t, re.S); return json.loads(m.group(0)) if m else {"verdict": "ошибка", "why": t[:120]}

L += ["", "## 2. Ссылки регламента на пункты — пункт существует и говорит то, что утверждается?", "",
      "| Утверждение регламента (кратко) | Ссылка | Пункт в тексте | Вердикт | Пояснение |", "|---|---|---|---|---|"]
stat = {}
for c in CL:
    b = base(c["doc"]); h, key = have(b); ref = f"{c['doc']}, {c['kind']} {c['point']}"
    short = c["sentence"][:150].replace("|", "/") + ("…" if len(c["sentence"]) > 150 else "")
    if not key:
        L.append(f"| {short} | {ref} | — | нет текста у нас | документ не скачан (статус: {STATUS.get(b, ('—',))[0]}) |"); stat["нет текста"] = stat.get("нет текста", 0) + 1; continue
    doc = IDX[key]
    if c["kind"] == "табл.":
        ocr = open(f"{ROOT}/build/ocr/" + doc["sources"][0] + ".txt", encoding="utf-8").read() if doc["points"] and any(p.get("ocr") for p in doc["points"].values()) else ""
        m = re.search(r"Таблица\s+" + re.escape(c["point"]) + r"\b", ocr)
        text = ocr[m.start(): m.start() + 2500] if m else None
    else:
        pt = doc["points"].get(c["point"]); text = pt["text"] if pt else None
    if text is None:
        why = "фрагмент — пункта нет в нашем тексте" if doc["kind"] == "fragment" else "пункт в тексте не найден"
        L.append(f"| {short} | {ref} | нет | {'нет текста у нас' if doc['kind'] == 'fragment' else 'пункт не найден'} | {why} |"); stat[why] = stat.get(why, 0) + 1; continue
    amend = [f"[{k}] {v['points'][c['point']]['text'][:800]}" for k, v in IDX.items() if k.startswith(key + " изм.") and c["point"] in v["points"]]
    res = llm(c["sentence"], key, f"{c['kind']} {c['point']}", text + ("\n\nИЗМЕНЕНИЯ К ПУНКТУ:\n" + "\n".join(amend) if amend else ""))
    note = (" · OCR" if h.endswith("(OCR)") else "") + (f" · пункт менялся ({', '.join(a.split(']')[0][1:].split(' изм. ')[1] for a in amend)})" if amend else "")
    L.append(f"| {short} | {ref} | есть{note} | **{res.get('verdict')}** | {str(res.get('why'))[:220].replace('|', '/')} |")
    stat[res.get("verdict")] = stat.get(res.get("verdict"), 0) + 1
L += ["", f"Итог по ссылкам на пункты: {stat}.", "",
      "Примечание: статусы — Росстандарт (protect.gost.ru) и docs.cntd.ru на 30.09.2026. Текст СП 17 распознан со скана (OCR) — "
      "дословные цитаты требуют сверки с оригиналом."]
open(f"{ROOT}/build/REGLAMENT_CHECK.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
