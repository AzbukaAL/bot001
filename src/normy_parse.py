#!/usr/bin/env python3
"""Разбор нормативов из materials/normy/ в индекс «документ → раздел → пункт» с редакцией и статусом.

Выход: build/normy_index.json  {doc_id: {title, edition, status, source, kind, sections{num: title}, points{num: {text, section}}}}
и build/normy_report.md — что разобрано, что нет (сканы, фрагменты, карточки).
Номера пунктов и цитаты дальше берутся ТОЛЬКО отсюда (правило проекта: ссылка на отсутствующий пункт = ответ не выдаётся).
"""
import json, os, re, subprocess, sys
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = f"{ROOT}/materials/normy"
OUT = f"{ROOT}/build"

# файл → (doc_id, редакция/примечание, статус). Статусы — из normy/REESTR.md (30.09.2026).
DOCS = {
    "SP_31-105-2002_cntd_fragment.html": ("СП 31-105-2002", "2002, фрагмент docs.cntd.ru", "рекомендательный; ФРАГМЕНТ, полного текста нет", "fragment"),
    "SP_256.1325800.2016_bez_izm.pdf": ("СП 256.1325800.2016", "исходная редакция, изм. № 1–9 НЕ учтены", "действует (с изм. 1–9)", "full"),
    "SP_256.1325800.2016_izm3.pdf": ("СП 256.1325800.2016 изм. 3", "Изменение № 3", "действует", "change"),
    "SP_256.1325800.2016_izm5.pdf": ("СП 256.1325800.2016 изм. 5", "Изменение № 5 (слабый текстовый слой)", "действует", "change"),
    "PUE7_gl_7.1_cntd_fragment.html": ("ПУЭ-7 гл. 7.1", "7-е изд., фрагмент docs.cntd.ru", "фрагмент", "fragment"),
    "PUE7_gl_7.1_garant_fragment.html": ("ПУЭ-7 гл. 7.1", "7-е изд., фрагмент Гарант (до 7.1.57)", "фрагмент", "fragment"),
    "PUE_gl_3.1_izd6_cntd_fragment.html": ("ПУЭ гл. 3.1", "6-е изд. (в составе сборника ПУЭ-7), фрагмент", "фрагмент", "fragment"),
    "GOST_30331.5-95_cntd_fragment.html": ("ГОСТ 30331.5-95", "фрагмент docs.cntd.ru", "действует по Росстандарту; двойник ГОСТ Р 50571.5-94 заменён ГОСТ Р 50571.4.43-2012", "fragment"),
    "GOST_R_50571.7.701-2024_cntd_fragment.html": ("ГОСТ Р 50571.7.701-2024", "фрагмент docs.cntd.ru", "действует с 01.08.2024", "fragment"),
    "SP_131.13330.2025.pdf": ("СП 131.13330.2025", "редакция 2025", "действует с 09.09.2025", "full"),
    "sp131-13330-2025.pdf": ("СП 131.13330.2025", "редакция 2025, текст от заказчика (27.10.2026)", "действует с 09.09.2025", "full"),
    "SP_131.13330.2020_zamenen_na_2025.pdf": ("СП 131.13330.2020", "редакция 2020", "УТРАТИЛ СИЛУ — заменён СП 131.13330.2025", "full"),
    "SP_50.13330.2024.pdf": ("СП 50.13330.2024", "редакция 2024", "действует с 16.06.2024", "full"),
    "SP_60.13330.2020_bez_izm.pdf": ("СП 60.13330.2020", "исходная редакция, изм. № 1–6 НЕ учтены", "действует (с изм. 1–6)", "full"),
    "SP_14.13330.2018_bez_izm.pdf": ("СП 14.13330.2018", "исходная редакция, изм. № 2–4 НЕ учтены (сканы)", "действует", "full"),
    "SP_64.13330.2017_bez_izm.pdf": ("СП 64.13330.2017", "исходная редакция, изм. № 1–4 НЕ учтены (сканы)", "действует", "full"),
    "SP_17.13330.2017_bez_izm.pdf": ("СП 17.13330.2017", "исходная редакция (скан, OCR), изм. № 1–5 распознаны отдельно", "действует; из регламента заказчика", "full"),
    "SP_20.13330.2016_bez_izm.pdf": ("СП 20.13330.2016", "исходная редакция, изм. № 1–6 НЕ учтены", "действует; ОЖИДАЕТ ПОДТВЕРЖДЕНИЯ ЗАКАЗЧИКА", "full"),
}
# 08.10.2026: полные тексты от заказчика — только в индекс v2 (`--v2` → build/normy_index_v2.json). Индекс v1 (бот, прогон №8) не меняется.
V2 = "--v2" in sys.argv
NEW_DOCS = {
    "sp31-105-2002-full.pdf": ("СП 31-105-2002", "2002, полный текст от заказчика (08.10.2026), вёрстка в две колонки",
                               "рекомендательный; полный текст от заказчика", "full"),
    "sp24-13330-2021.pdf": ("СП 24.13330.2021", "2021 от заказчика (08.10.2026); изм. № 1–2 в файле не учтены", "действует (с изм. 1–2)", "full"),
}
COLUMNS = {"sp31-105-2002-full.pdf"}                       # двухколоночная вёрстка → src/pdf_columns.py
FRAGMENT_REPLACED = {"SP_31-105-2002_cntd_fragment.html"}   # в v2 вытесняется полным текстом
if V2: DOCS = {**{k: v for k, v in DOCS.items() if k not in FRAGMENT_REPLACED}, **NEW_DOCS}
BASE = {"SP_17.13330.2017": "СП 17.13330.2017", "SP_14.13330.2018": "СП 14.13330.2018", "SP_256.1325800.2016": "СП 256.1325800.2016", "SP_60.13330.2020": "СП 60.13330.2020",
        "SP_64.13330.2017": "СП 64.13330.2017", "SP_20.13330.2016": "СП 20.13330.2016"}
OCR_DIR = f"{ROOT}/build/ocr"
AM = re.compile(r"(?:^|\n)\s*((?:Пункт|Подпункт|Подраздел|Раздел|Таблица|Приложение)\s+([\dА-Я][\d.]*[\dА-Я]?))", re.I)

HYPH_STAT = {"слито": 0, "дефис": 0, "по умолчанию": 0}
HYPH = re.compile(r"([A-Za-zА-Яа-яЁё]+)[-\u00ad\u2010][ \t]*\n[ \t]*([a-zа-яё]+)(\S*)[ \t]*")

NUM_START = re.compile(r"\d{1,3}(?:\.\d{1,3}){1,4}\.?(?:\s|$)")

def join_hyphens(text):
    """17.10: перенос строки в PDF («уси-» / «лия») склеивается до разбора — иначе в индексе «уси- лия», и цитата,
    которую модель пишет правильно («усилия»), не проходит сверку дословности (K031, СП 17 п. 7.8).
    Перенос мог прийтись на настоящий дефис — решает словарь самого документа: склеенное слово в тексте есть → склеиваем;
    есть форма через дефис → дефис без пробела; иначе склеиваем (перенос слога встречается намного чаще).
    На предыдущую строку уходит только остаток слова с прилегающей пунктуацией, разбивка строк сохраняется: иначе
    строка с номером пункта получала хвост следующей строки, кончалась числом и читалась как оглавление (пропадали пункты)."""
    vocab = set(re.findall(r"[a-zа-яё]+(?:-[a-zа-яё]+)*", text.lower()))
    def fix(m):
        rest = m.string[m.end():m.string.find("\n", m.end()) if "\n" in m.string[m.end():] else len(m.string)]
        # остаток строки похож на номер пункта («лице 7.23 СП 52…») — сливаем строку целиком, иначе он станет «пунктом 7.23»
        a, b, tail = m.group(1), m.group(2), m.group(3) + (" " if NUM_START.match(rest) else "\n")
        if (a + b).lower() in vocab: HYPH_STAT["слито"] += 1; return a + b + tail
        if f"{a}-{b}".lower() in vocab: HYPH_STAT["дефис"] += 1; return f"{a}-{b}" + tail
        HYPH_STAT["по умолчанию"] += 1; return a + b + tail
    return HYPH.sub(fix, text)

def parse_amendment(text):
    """Изменение к СП: «Пункт 5.3 изложить в новой редакции: …» → {номер: текст}. Плюс обычные нумерованные пункты."""
    pts = {}
    text = join_hyphens(text)
    ms = list(AM.finditer(text))
    for i, m in enumerate(ms):
        seg = text[m.start():ms[i + 1].start() if i + 1 < len(ms) else len(text)]
        num = m.group(2).rstrip(".")
        seg = re.sub(r"\s{2,}", " ", seg).strip()
        if len(seg) > 30 and (num not in pts or len(seg) > len(pts[num]["text"])): pts[num] = {"text": seg[:6000], "section": None}
    for k, v in parse(text)[1].items():
        if k not in pts and len(v["text"]) > 30: pts[k] = v
    return pts
SKIP_NOTE = {"_kartochka_": "карточка статуса, не текст", "izm1_OTMENENO": "изменение отменено — не индексируем"}

PT = re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3}){1,4})\.?\s+(\S.{2,})$")
PT_BARE = re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3}){1,4})\.\s*$")   # «7.1.3.» — номер отдельной строкой, текст ниже
SEC = re.compile(r"^\s*(\d{1,2})\s+([А-ЯЁ][А-Яа-яЁё ,\-–()]{3,90})\s*$")
TOC = re.compile(r"(\.\s?){5,}|…{3,}|\s\d{1,3}\s*$")

def pdf_text(p):
    return subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True).stdout

def html_text(p):
    soup = BeautifulSoup(open(p, "rb").read(), "html.parser")   # байтами: кодировку (cp1251 у Гаранта) берёт из meta
    for t in soup(["script", "style", "nav", "header", "footer"]): t.decompose()
    return soup.get_text("\n")

def parse(text):
    sections, points, cur_sec, cur = {}, {}, None, None
    text = join_hyphens(text)
    for raw in text.split("\n"):
        line = raw.replace("\xa0", " ").strip()
        if not line: continue
        m = PT.match(line)
        if m and not TOC.search(line) and not re.fullmatch(r"[\d.,\s]+", m.group(2)) and m.group(2)[0].isalpha() or (m and m.group(2)[:1] in "«\""):
            num = m.group(1)
            cur = num
            txt = m.group(2)
            if num not in points or len(points[num]["text"]) < 40 or TOC.search(points[num]["text"][:200]):   # 08.10: строка оглавления не держит номер (СП 24, 7.7)
                points[num] = {"text": txt, "section": cur_sec}
            else:
                cur = None   # повтор (обычно оглавление после тела) — не перезаписываем
            continue
        b = PT_BARE.match(line)
        if b:
            cur = b.group(1)
            if cur not in points or TOC.search(points[cur]["text"][:200]): points[cur] = {"text": "", "section": cur_sec}
            elif len(points[cur]["text"]) >= 40: cur = None
            continue
        s = SEC.match(line)
        if s and not TOC.search(line) and int(s.group(1)) <= 20:
            sections.setdefault(s.group(1), s.group(2).strip()); cur_sec = s.group(1); cur = None
            continue
        if cur and len(points[cur]["text"]) < 6000:
            points[cur]["text"] += " " + line
    for v in points.values(): v["text"] = re.sub(r"\s{2,}", " ", v["text"]).strip()
    return sections, points

def main():
    os.makedirs(OUT, exist_ok=True)
    idx, rep = {}, ["# Разбор нормативов — прогон №1", "", "| Документ | Файл | Вид | Пунктов | Разделов | Статус |", "|---|---|---|---|---|---|"]
    notes = []
    for f in sorted(os.listdir(N)):
        p = os.path.join(N, f)
        if f in DOCS:
            doc, ed, status, kind = DOCS[f]
            ocr_txt = f"{ROOT}/build/ocr/{f}.txt"
            is_scan = f.endswith(".pdf") and os.path.exists(ocr_txt)      # скан основного текста (СП 17) — берём OCR, помечаем ocr
            if f in COLUMNS:
                from pdf_columns import pdf_text_columns; text = pdf_text_columns(p)
            else:
                text = open(ocr_txt, encoding="utf-8").read() if is_scan else (pdf_text(p) if f.endswith(".pdf") else html_text(p))
            secs, pts = parse(text)
            d = idx.setdefault(doc, {"title": doc, "edition": ed, "status": status, "kind": kind, "sources": [], "sections": {}, "points": {}})
            d["sources"].append(f)
            d["sections"].update({k: v for k, v in secs.items() if k not in d["sections"]})
            for k, v in pts.items():
                if k not in d["points"] or len(v["text"]) > len(d["points"][k]["text"]):
                    v["source"] = f; v["ocr"] = bool(is_scan) or v.get("ocr", False); d["points"][k] = v
            rep.append(f"| {doc} | {f} | {kind} | {len(pts)} | {len(secs)} | {status} |")
            if len(pts) < 20 and kind != "fragment": notes.append(f"- ⚠ {f}: всего {len(pts)} пунктов — текстовый слой слабый/скан, проверить.")
        elif f.endswith(".pdf"):
            chars = len(pdf_text(p).strip())
            notes.append(f"- ❌ {f}: не разобран — {'скан без текстового слоя (нужно распознавание)' if chars < 200 else 'нет в карте документов'}")
        elif f.endswith(".html"):
            why = next((w for k, w in SKIP_NOTE.items() if k in f), "нет в карте документов")
            notes.append(f"- ➖ {f}: {why}")
    # изменения к СП: распознанные (OCR, ocr=true) и с текстовым слоем (изм. 3 к СП 256)
    for f in sorted(os.listdir(N)):
        m = re.match(r"(SP_[\d.]+)_izm(\d+)", f)
        if not m or "OTMENENO" in f or m.group(1) not in BASE: continue
        o = os.path.join(OCR_DIR, f + ".txt"); is_ocr = os.path.exists(o)
        text = open(o, encoding="utf-8").read() if is_ocr else pdf_text(os.path.join(N, f))
        pts = parse_amendment(text)
        doc = f"{BASE[m.group(1)]} изм. {m.group(2)}"
        for v in pts.values(): v["ocr"] = is_ocr; v["source"] = f
        idx[doc] = {"title": doc, "edition": f"Изменение № {m.group(2)}" + (" (распознано OCR — цитаты только после сверки)" if is_ocr else ""),
                    "status": "действует", "kind": "change", "ocr": is_ocr, "sources": [f], "sections": {}, "points": pts}
        idx.pop(f"{BASE[m.group(1)]} изм. {m.group(2)}".replace(" изм.", " изм.").strip() + "_", None)
        rep.append(f"| {doc} | {f} | change{' OCR' if is_ocr else ''} | {len(pts)} | 0 | действует |")
        notes[:] = [n for n in notes if f not in n]
        if not pts: notes.append(f"- ⚠ {f}: изменение разобрано, но пунктов не выделено — {'OCR' if is_ocr else 'текст'} проверить")
    # 27.10.2026: климатические таблицы 5.1, 6.1, 7.1 СП 131 — построчно, пункт за пунктом (src/climate_sp131.py; копия заказчика,
    # сверка с копией Минстроя). Ключ «таблицы …, <пункт>» не начинается с цифры → в поиск run08 (PTS) строки не идут и
    # кандидатов не вытесняют; числа из них берёт код (src/calc_teplo.py), модель — нет. В словарь pdn_check пункты попадают.
    import climate_sp131 as CL
    clim, _ = CL.build()
    d131 = idx.get("СП 131.13330.2025")
    if d131:
        for name, c in clim.items():
            d131["points"][f"таблицы 5.1–7.1, {name}"] = {"text": CL.point_text(name, c), "section": "5", "source": CL.PRIMARY,
                                                          "ocr": False, "table": True, "checked": c["checked"]}
        rep.append(f"| СП 131.13330.2025 (климатические таблицы по пунктам) | {CL.PRIMARY} | table | {len(clim)} | 0 | "
                   f"сверено с копией Минстроя: {sum(c['checked'] for c in clim.values())} из {len(clim)} |")
    # 30.09 (прогон №3): цитата не выдаётся до сверки (quote_hold) —
    #  а) весь СП 20.13330.2016: изм. 2–4 легально не получены, какие пункты они меняют — не определить;
    #  б) пункты базовых СП, которые упоминаются в распознанных изменениях — исходный текст мог устареть.
    hold = 0
    # 08.10.2026: двухколоночный PDF — пункт с вероятной примесью таблицы/соседней колонки цитате не отдаётся до сверки:
    # раздел не совпадает с номером пункта (7.3.5.2 → «раздел 3») или ≥6 чисел подряд (ячейки таблицы, 8.2.2.6).
    for f in COLUMNS & set(DOCS):
        d = idx.get(DOCS[f][0])
        for num, v in (d or {}).get("points", {}).items():
            if v.get("source") != f: continue
            mixed = v.get("section") and str(v["section"]) != num.split(".")[0]
            toks = v["text"].split()
            table = any(sum(any(ch.isdigit() for ch in t) for t in toks[i:i + 8]) >= 6 for i in range(max(1, len(toks) - 7)))
            if mixed or table:
                v["quote_hold"] = "двухколоночный PDF: возможна примесь таблицы или соседней колонки — сверить с оригиналом"; hold += 1
    for doc, d in idx.items():
        if doc == "СП 20.13330.2016":
            for v in d["points"].values(): v["quote_hold"] = "изм. № 2–4 к СП 20 не получены — текст пункта мог измениться"; hold += 1
    for doc, d in list(idx.items()):
        m = re.match(r"(.+) изм\. (\d+)$", doc)
        if not m or m.group(1) not in idx: continue
        for num in d["points"]:
            bp = idx[m.group(1)]["points"].get(num)
            if bp is not None and "quote_hold" not in bp:
                bp["quote_hold"] = f"пункт затронут изм. № {m.group(2)} — исходный текст мог устареть"; hold += 1
    rep.append(f"\nЦитата не выдаётся до сверки (quote_hold): {hold} пунктов базовых текстов.")
    sfx = "_v2" if V2 else ""
    json.dump(idx, open(f"{OUT}/normy_index{sfx}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rep += ["", "## Не разобрано / ограничения", *notes, "",
            "## Итог по документам", *[f"- {k}: {len(v['points'])} пунктов ({v['kind']}; {v['edition']})" for k, v in idx.items()]]
    open(f"{OUT}/normy_report{sfx}.md", "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print("\n".join(rep))
    print("переносы строк:", HYPH_STAT)

if __name__ == "__main__":
    main()
