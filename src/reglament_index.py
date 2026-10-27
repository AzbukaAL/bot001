"""Индекс «стандарт компании» (отдельный тип источника, НЕ норматив) + перечень ссылок на документы и пункты.
Вход: build/reglament/*.lines.json (уже обезличено). Выход: build/reglament_index.json, build/reglament_refs.json."""
import json, os, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = f"{ROOT}/build/reglament"
SRC = {"voprosy-i-otvety.docx": "СК-ВО", "otvety-dlya-chat-bota.odt": "СК-ЧБ"}

def chunks(text, n=1200):
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", text):
        if len(cur) + len(s) > n and cur: parts.append(cur.strip()); cur = ""
        cur += " " + s
    if cur.strip(): parts.append(cur.strip())
    return parts

idx = {}
# docx: 17 блоков; «2» отдельным абзацем — склеить со следующим
L = [t for _, t in json.load(open(f"{B}/voprosy-i-otvety.docx.lines.json", encoding="utf-8"))]
blocks, i = [], 0
while i < len(L):
    t = L[i]
    if re.fullmatch(r"\d{1,2}", t.strip()) and i + 1 < len(L): t = t.strip() + " " + L[i + 1]; i += 1
    blocks.append(t); i += 1
for t in blocks:
    m = re.match(r"\s*(\d{1,2})\.?\s+(.{3,80}?)(?=\s{2,}|\s+ВОПРОСЫ|$)", t)
    num, title = (m.group(1), m.group(2).strip()) if m else ("?", t[:60])
    for k, c in enumerate(chunks(t), 1):
        idx[f"СК-ВО §{num}.{k}"] = {"source": "voprosy-i-otvety.docx", "block": num, "title": title, "text": c}
# odt: разделы по заголовкам и нумерованным темам
L = json.load(open(f"{B}/otvety-dlya-chat-bota.odt.lines.json", encoding="utf-8"))
sec, buf, n = "вводный", [], 0
def flush():
    global n
    if buf:
        n += 1
        for k, c in enumerate(chunks(" ".join(buf)), 1):
            idx[f"СК-ЧБ §{n}.{k}"] = {"source": "otvety-dlya-chat-bota.odt", "block": str(n), "title": sec, "text": c}
for s, t in L:
    if s == "heading" or re.match(r"^\s*\d{1,2}\.\s+\S", t):
        flush(); buf.clear(); sec = t[:80]
    buf.append(t)
flush()

# 15.10.2026: позиция инженера заказчика — отдельный фрагмент стандарта компании (СК-ИНЖ).
# Источник — materials/reglament/poziciya-inzhenera-<ГГГГММДД>.md; индексируется только текст ПОСЛЕ разделителя «---».
import glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
from anonymize import anonymize
for num, f in enumerate(sorted(glob.glob(f"{ROOT}/materials/reglament/poziciya-inzhenera-*.md")), 1):
    raw = anonymize(open(f, encoding="utf-8").read())[0]
    title = raw.split("\n", 1)[0].lstrip("# ").strip()
    body = " ".join(raw.split("\n---\n", 1)[1].split()) if "\n---\n" in raw else ""
    if not body: print(f"ПРОПУЩЕН (нет текста после «---»): {f}"); continue
    m = re.search(r"(\d{4})(\d{2})(\d{2})", os.path.basename(f))
    date = f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else ""
    # 16.10: позиция инженера — один кусок (1600 символов): при пороге 1200 дописанная фраза отрезала последнее
    # предложение в §1.2, и в основание попадала только часть позиции
    # 19.10: «Раздел:» и «Источник:» из шапки (до «---») — для подписи раздела инженеру; у позиции 15.10 их нет
    head = raw.split("\n---\n", 1)[0]
    meta = {k: (re.search(rf"^{w}:\s*(.+)$", head, re.M) or [None, None])[1] for k, w in (("section_name", "Раздел"), ("source_person", "Источник"))}
    for k, c in enumerate(chunks(body, 1600), 1):
        idx[f"СК-ИНЖ §{num}.{k}"] = {"source": os.path.basename(f), "block": str(num), "title": title, "text": c, "date": date,
                                     **{k2: v for k2, v in meta.items() if v}}

json.dump(idx, open(f"{ROOT}/build/reglament_index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ── ссылки на документы и пункты ──
DOC = re.compile(r"\b(ГОСТ\s?Р?\s?(?:ИСО|EN|МЭК)?\s?[\d.\-–]+(?:-\d{2,4})?|СП\s?[\d.]+(?:-\d{2,4})?|СНиП\s?[\d.\-–]+(?:-\d{2,4})?|СанПиН\s?[\d.\-–]+|"
                 r"ПУЭ(?:-?7)?|Федеральн\w+ закон\w*[^.;]{0,40}?№\s?\d+-ФЗ|\d{2,3}-ФЗ|ТР ТС\s?\d+/\d+|Eurocode\s?\d|EN\s?\d{3,5}(?:-\d)*|DIN\s?\d+|ISO\s?\d+|СТО\s?[\d\-.]+|ТУ\s?[\d.\-]+)", re.I)
PT = re.compile(r"(?:п\.|пп\.|пункт[аеу]?|раздел[аеу]?|табл\.|таблиц[аеуы])\s*([\dА-Я][\d.,\sи–\-]{0,20})", re.I)
refs = collections.defaultdict(lambda: {"count": 0, "files": set(), "points": set(), "contexts": []})
for k, v in idx.items():
    for m in DOC.finditer(v["text"]):
        d = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".,")
        d = re.sub(r"^(ГОСТ|СП|СНиП)\s?", lambda x: x.group(1) + " ", d)
        r = refs[d]; r["count"] += 1; r["files"].add(v["source"])
        tail = v["text"][max(0, m.start() - 160): m.end() + 120]
        for p in PT.finditer(v["text"][max(0, m.start() - 60): m.end() + 60]):
            r["points"].add(p.group(0).strip(" ,.;"))
        if len(r["contexts"]) < 6: r["contexts"].append({"id": k, "text": tail})
out = {d: {**r, "files": sorted(r["files"]), "points": sorted(r["points"])} for d, r in refs.items()}
json.dump(out, open(f"{ROOT}/build/reglament_refs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"индекс «стандарт компании»: {len(idx)} фрагментов "
      f"(СК-ВО блоков {len({v['block'] for v in idx.values() if v['source'].endswith('docx')})}, "
      f"СК-ЧБ разделов {len({v['block'] for v in idx.values() if v['source'].endswith('odt')})})")
print(f"упомянутых документов: {len(out)}")
for d, r in sorted(out.items(), key=lambda x: -x[1]["count"]):
    print(f"  {d:34} ×{r['count']:<3} {'ВО' if any(f.endswith('docx') for f in r['files']) else '  '}{'ЧБ' if any(f.endswith('odt') for f in r['files']) else '  '} {', '.join(r['points'])[:90]}")
