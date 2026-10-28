"""Данные проекта к претензии — не только КП (15.10.2026, задание Вадима).
Принимаем три вида PDF: КП (разбор src/object_index.py), опросный лист (заполняет покупатель: выделенная мощность
и фазность, отопление, НЭВН, вентиляция) и теплотехнический расчёт объекта. К одной претензии — несколько файлов.
Вид документа определяется по тексту, дата — из метаданных PDF (CreationDate), источник каждой позиции — «<вид> от <дата>».
Всё текстовое — через обезличиватель (правило 1 и 7 проекта).

🔴 Опросный лист с пустой колонкой отметок — это бланк, а не данные проекта: позиций не даёт, причина возвращается
в поле note (16.10.2026: присланный заказчиком файл — ровно такой бланк).

  python3 src/project_docs.py materials/objects/oprosnyi-list-kotel.pdf materials/objects/teplotekh-raschet-kotel.pdf
"""
import os
import collections, json, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
from anonymize import anonymize
import pdfplumber
import object_index as OI, base_versions as BV

def A(t): return anonymize(" ".join((t or "").split()))[0]

def text_of(path):
    return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout

# 21.10.2026 (решение Вадима, документы 52Р5): скан без текстового слоя — распознавание на Питере (tesseract rus),
# кэш по md5 файла в build/ocr-cache (600). Всё, что взято со скана, помечается ocr — покупателю без сверки не идёт.
OCR_CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "ocr-cache")

def ocr_text(path):
    import glob, hashlib, tempfile
    h = hashlib.md5(open(path, "rb").read()).hexdigest(); c = f"{OCR_CACHE}/{h}.txt"
    if os.path.exists(c): return open(c, encoding="utf-8").read()
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", "300", "-png", path, f"{td}/p"], check=True)
        t = "\n".join(subprocess.run(["tesseract", q, "-", "-l", "rus", "--psm", "6"], capture_output=True, text=True).stdout
                      for q in sorted(glob.glob(f"{td}/p*.png")))
    os.makedirs(OCR_CACHE, mode=0o700, exist_ok=True); open(c, "w", encoding="utf-8").write(t); os.chmod(c, 0o600)
    return t

def needs_ocr(path):
    """21.10: файл — скан, и распознавания в кэше ещё нет (будет долго: 1–2 минуты на документ)."""
    import hashlib
    try:
        if not path.lower().endswith(".pdf") or len(text_of(path).strip()) >= 200: return False
        return not os.path.exists(f"{OCR_CACHE}/{hashlib.md5(open(path, 'rb').read()).hexdigest()}.txt")
    except Exception: return False

def text_or_ocr(path):
    """(текст, со_скана): текстовый слой; почти пустой — распознавание."""
    t = text_of(path)
    return (t, False) if len(t.strip()) >= 200 else (ocr_text(path), True)

KINDS = [("техническое описание", r"(?-i:ТЕХНИЧЕСКОЕ\s+ОПИСАНИЕ)"),   # 21.10: заголовок приложения «ТО» прописными — с учётом
                                                                     # регистра: «по техническому описанию» в оценке ChatGPT — не ТО
         ("смета", r"смет[аы]\s+на\s+строительств|локальн\w*\s+смет"),
         ("спецификация окон", r"Изделие\s*№[\s\S]{0,600}?(?:Профиль|Заполнение)"),
         ("опросный лист", r"Опросный\s+лист"),
         ("теплотехнический расчёт", r"Требуемая\s+мощность\s+котла|ВЫБОР\s+ГОРОДА"),
         ("КП", r"Площадь\s+застройки|Адрес\s+об[ьъ]екта")]

def kind(path, text=None):
    """Вид документа по тексту; None — не узнали (отвечать без данных проекта и сказать об этом)."""
    t = text if text is not None else text_of(path)
    return next((k for k, rx in KINDS if re.search(rx, t, re.I)), None)

def date_of(path):
    return OI.kp_date(path)

# ── опросный лист: отметки покупателя ──
MARK = re.compile(r"^(?:[VvХхXx+✓√]|да)$", re.I)

def _lines(pg, tol=3):
    """Слова страницы → строки (по вертикали), каждая — список слов слева направо."""
    rows = collections.defaultdict(list)
    for w in pg.extract_words(): rows[round(w["top"] / tol)].append(w)
    return [sorted(rows[k], key=lambda w: w["x0"]) for k in sorted(rows)]

def oprosnyi(path):
    """Опросный лист → отмеченные строки. Отметка — знак или рисунок в колонке «V» на строке варианта.
    Возвращает {items, marks, note}: items пуст и note заполнен, если отметок нет (бланк)."""
    with pdfplumber.open(path) as pdf:
        pg = pdf.pages[0]
        words = pg.extract_words()
        head = next((w for w in words if w["text"].strip() == "V" and w["top"] < 120), None)
        if not head:
            return {"items": [], "marks": 0, "note": "в листе не найдена колонка отметок «V» — файл не похож на опросный лист"}
        cx = (head["x0"] + head["x1"]) / 2
        xs = sorted({round(l["x0"]) for l in pg.lines if abs(l["x0"] - l["x1"]) < 1})
        VX0 = max([x for x in xs if x < cx - 2], default=cx - 25)
        VX1 = min([x for x in xs if x > cx + 2], default=cx + 25)
        fills = [r for r in pg.rects if r.get("non_stroking_color") and r["non_stroking_color"] != (0, 0, 0)]
        # всё, что нарисовано или написано ВНУТРИ колонки отметок (границы колонки и строк — не отметка)
        marks = [{"x": (w["x0"] + w["x1"]) / 2, "top": w["top"], "bottom": w["bottom"], "what": w["text"]}
                 for w in words if VX0 + 1 < (w["x0"] + w["x1"]) / 2 < VX1 - 1 and w is not head and MARK.match(w["text"].strip())]
        for o in list(pg.lines) + list(pg.curves) + [r for r in pg.rects if r not in fills]:
            if o["x0"] > VX0 + 1 and o["x1"] < VX1 - 1 and o["top"] > head["bottom"]:
                marks.append({"x": (o["x0"] + o["x1"]) / 2, "top": o["top"], "bottom": o["bottom"], "what": "рисунок"})

        section, sub, items, rows = "", "", [], []
        for ws in _lines(pg):
            x0, x1 = min(w["x0"] for w in ws), max(w["x1"] for w in ws)
            y0, y1 = min(w["top"] for w in ws), max(w["bottom"] for w in ws)
            txt = " ".join(w["text"] for w in ws)
            if y0 < head["bottom"] or re.match(r"Страница|Дата_", txt): continue
            filled = any(r["x0"] < x0 + 2 and r["top"] - 2 <= y0 and y1 <= r["bottom"] + 2 for r in fills)
            if filled:
                if x0 < VX0 - 80: section, sub = txt, ""      # раздел листа («Электрика»)
                else: sub = txt                                # подзаголовок («Выделенная мощность кВт и фазность»)
                continue
            label = " ".join(w["text"] for w in ws if w["x1"] <= VX0 + 2)
            note = " ".join(w["text"] for w in ws if w["x0"] >= VX1 - 2)
            if not label:
                if rows and note: rows[-1]["note"] += " " + note     # примечание в несколько строк
                continue
            # Строки варианта НЕ склеиваются: «5кВт, 1фаза», «15кВт, 3фазы» и «другое» — три разных варианта в одной
            # клетке отметок, и склейка выдала бы за данные проекта весь перечень. Цена: название варианта,
            # перенесённое на вторую строку («Розетка для подключения сплит-/систем'ы'»), в описании обрезано.
            rows.append({"section": section, "sub": sub, "label": label, "note": note, "y0": y0, "y1": y1})

        for r in rows:
            hit = [m for m in marks if r["y0"] - 4 <= (m["top"] + m["bottom"]) / 2 <= r["y1"] + 4]
            if not hit: continue
            # В описание идёт ТОЛЬКО отмеченная строка листа: примечание формы переносится в листе на соседние строки,
            # и его обрывок, попав в основание, читался бы покупателем как данные его проекта.
            items.append({"позиция": A(r["sub"] or r["section"] or "опросный лист"),
                          "описание": A(r["label"]), "примечание_листа": A(r["note"]) or None,

                          "отметка": ", ".join(sorted({m["what"] for m in hit}))})
        note = None if items else ("в опросном листе нет ни одной отметки — это незаполненный бланк, "
                                   "данных выделенной мощности, фазности и опций в нём нет")
        return {"items": items, "marks": len(marks), "note": note}

# ── теплотехнический расчёт: перечень параметров (белый список — что умеем читать) ──
TEPLO = [("Город (место строительства)", r"ВЫБОР ГОРОДА\s+([А-ЯЁA-Z][^\s]{2,})"),
         ("Расчётная температура наружного воздуха, °C", r"Расчетная t\S*\s+(-?\d+)"),
         ("Тип дома", r"Тип дома\s+(.+?)(?=\s+фактическое|\s+Утеплитель)"),   # «ИТОГ ПО ДОМУ»: в шапке значение разорвано строкой
         ("Наружная обшивка каркаса", r"Наружная обшивка каркаса\s+(\S+)"),
         ("Внутренняя обшивка каркаса", r"Внутренняя обшивка каркаса\s+(\S+)"),
         ("Размер дома (фронтонный × боковой), м", r"Размер А \(фронтонный\), м\s+([\d,]+).{0,80}?Размер Б \(боковой\), м\s+([\d,]+)"),
         ("Высота этажа, м", r"Высота этажа \(h_эт\), м\s+([\d,]+)"),
         ("Площадь остекления, м²", r"Площадь остекления, м²\s+([\d,]+)"),
         ("Утеплитель стен, мм", r"Утеплитель стен, мм\s+(\d+)"),
         ("Утеплитель пола, мм", r"Утеплитель пола, мм\s+(\d+)"),
         ("Утеплитель потолка, мм", r"Утеплитель потолка, мм\s+(\d+)"),
         ("Стеклопакет", r"Стеклопакет\s+(.+?)(?=\s{2,}|\s+класс)"),
         ("Рекуператоры, шт.", r"Рекуператоры, шт\.\s+(\d+)"),
         ("Общие теплопотери здания, кВт·ч/год", r"Общие теплопотери здания, кВт\*ч/год\s+(?:.*?)(\d{3,6})(?=\s)"),
         ("Требуемая мощность котла, кВт", r"Требуемая мощность котла, кВт\s+([\d,]+)"),
         ("Фактическая мощность устанавливаемого котла, кВт", r"Фактическая мощность устанавливаемого котла, кВт\s+([\d,]+)")]

def teplo(path, text=None):
    """Теплотехнический расчёт → параметры объекта из белого списка TEPLO. Чего в списке нет — не читаем (молча не выдумываем)."""
    flat = A(text if text is not None else text_of(path))
    items = []
    for name, rx in TEPLO:
        m = re.search(rx, flat)
        if m: items.append({"позиция": name, "описание": " × ".join(g for g in m.groups() if g)})
    req = next((i for i in items if i["позиция"].startswith("Требуемая мощность котла")), None)
    fact = next((i for i in items if i["позиция"].startswith("Фактическая мощность")), None)
    if req and fact:   # ставится ФАКТИЧЕСКАЯ мощность: по отдельности в основания попадала только требуемая
        items = [i for i in items if i is not req and i is not fact] + \
                [{"позиция": "Мощность котла, кВт", "описание": f"требуемая по расчёту {req['описание']}, "
                                                                f"фактическая устанавливаемая {fact['описание']}"}]
    note = None if items else "в теплотехническом расчёте не распознан ни один параметр из известных системе"
    return {"items": items, "marks": None, "note": note}

# ── КП (как было, src/object_index.py) ──
def kp(path):
    d = OI.build(path, "КП покупателя")
    meta = [{"позиция": k, "описание": str(d["meta"][key])} for k, key in
            [("Адрес объекта", "населённый пункт"), ("Площадь застройки", "площадь застройки"),
             ("Класс энергоэффективности", "класс энергоэффективности"), ("Размер дома", "размер")] if d["meta"].get(key)]
    return {"items": meta + d["items"], "marks": None, "note": None if d["items"] else "в КП не распознано ни одной позиции"}

# ── 21.10.2026: техническое описание, смета, спецификация окон ──
NOISE = re.compile(r"_{3,}|/\s*/|Приложение\s*№|ТЕХНИЧЕСК\w*\s+ОПИСАНИ|КОМПЛЕКТА|ЗНАЧЕНИЕ")
# строки подписей и реквизитов сторон — не данные проекта (в них ФИО, инициалы, адреса; распознавание добавляет мусор)
SIGN = re.compile(r"(?i)заказчик|подрядчик|ознакомлен|претензий\s+не\s+име|подпис|м\.\s?п\.|\bадрес|паспорт|выдан|"
                  r"(?-i:\b[А-ЯЁ]\.\s?[А-ЯЁ]\.|/\s*[А-ЯЁ])")   # инициалы и «/Фамилия» — с учётом регистра («кг/куб.м» — не подпись)

def keep_line(raw):
    """21.10: строка годится в данные проекта — не шум, не подпись/реквизиты, после обезличивания без меток ПДн."""
    return bool(raw.strip()) and not NOISE.search(raw) and not SIGN.search(raw) and "<" not in anonymize(raw)[0]
CAP2 = re.compile(r"^(.{3,80}?[а-яё0-9)])\s+([А-ЯЁ][а-яё].*)$")   # «Лаги цокольного перекрытия | Брус 38х190…»

def to_doc(path, text=None):
    """Техническое описание (таблица «параметр — значение»): строка с заглавной — новая позиция, со строчной/цифры —
    продолжение. Параметр и значение делятся по второму слову с заглавной («Обвязочный брус Брус срощенный 114х140»)."""
    t, scan = text_or_ocr(path) if text is None else (text, False)
    rows = []
    for line in t.splitlines():
        l = re.sub(r"^[\s|.,]*(?:\d{1,2}[.)])?[\s|.]*", "", line).replace("|", " ").strip()
        if not l or not keep_line(line): continue
        if l[0].isupper() or not rows: rows.append(l)
        else: rows[-1] += " " + l
    items = []
    for r in rows:
        r = " ".join(r.split())
        if len(r) < 8 or sum(ch.isalpha() for ch in r) < 6: continue
        m = CAP2.match(r)
        pos, desc = (m.group(1), m.group(2)) if m else (r[:60], r)
        if "<" in A(pos) + A(desc): continue   # страховка: метка ПДн в позиции — не берём
        items.append({"позиция": A(pos), "описание": A(desc), "ocr": scan})
    return {"items": items, "marks": None, "note": None if items else "в техническом описании не распознано позиций"}

def _vocab():
    B = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build")
    W = re.compile(r"[а-яё]{4,}"); v = set()
    for d in json.load(open(f"{B}/normy_index.json", encoding="utf-8")).values():
        for p in d["points"].values(): v.update(W.findall(p["text"].lower()))
    for x in json.load(open(f"{B}/reglament_index.json", encoding="utf-8")).values(): v.update(W.findall(x.get("text", "").lower()))
    return v

def smeta(path, text=None):
    """Смета (обычно скан таблицы — распознаётся с шумом): берём только читаемое — шапку (площадь, этажность),
    итоги по разделам и строки, где ≥ 80 % слов есть в словаре норм и регламента."""
    t, scan = text_or_ocr(path) if text is None else (text, False)
    V = _vocab(); items = []
    flat = " ".join(t.split())
    m = re.search(r"площадь\s+объекта\s*([\d.,]+)\s*кв\.?\s*м", flat, re.I)
    if m: items.append({"позиция": "Площадь объекта (смета)", "описание": f"{m.group(1)} кв. м", "ocr": scan})
    m = re.search(r"количество\s+этажей\s*[-–—]?\s*([^,.;]{1,20}мансард\w*|\d)", flat, re.I)
    if m: items.append({"позиция": "Количество этажей (смета)", "описание": A(m.group(1)), "ocr": scan})
    for line in t.splitlines():
        l = " ".join(line.replace("|", " ").split())
        if not l or not keep_line(line): continue
        r = re.match(r"(?i)работа\s+по\s+разделу\s*(\d+)\)?.*?([\d\s]{4,}[\d])\s*$", l)
        if r: items.append({"позиция": f"Итог по разделу {r.group(1)} (смета)", "описание": A(l), "ocr": scan}); continue
        words = re.findall(r"[а-яё]{4,}", l.lower())
        if len(words) >= 3 and sum(w in V for w in words) / len(words) >= 0.8:
            items.append({"позиция": "Позиция сметы", "описание": A(l), "ocr": scan})
    return {"items": items, "marks": None, "note": None if items else "в смете не распознано читаемых позиций"}

def windows(path, text=None):
    """Спецификация окон и дверей (текстовый слой, «Изделие №: N»): тип, профиль, размер, заполнение, количество."""
    t, scan = text_or_ocr(path) if text is None else (text, False)
    items = []
    for blk in re.split(r"Изделие\s*№:?\s*", t)[1:]:
        num = re.match(r"\d+", blk); f = lambda rx: (re.search(rx, blk) or [None, None])[1]
        prof = f(r"Профиль\s+([^\n]+)"); size = re.search(r"\((\d{3,4})\s*[xх×]\s*(\d{3,4})\)", blk)
        fill = f(r"Заполнение\s+(\S+)"); qty = f(r"Количество\s+(\d+)\s*шт")
        kind_ = "дверь" if re.search(r"(?i)дверь|дверн", prof or blk[:300]) else "окно"
        parts = [f"профиль {' '.join(prof.split())}" if prof else None, f"размер {size.group(1)}×{size.group(2)} мм" if size else None,
                 f"заполнение (стеклопакет) {fill}" if fill else None, f"{qty} шт." if qty else None]
        if any(parts): items.append({"позиция": f"Окна и двери: изделие {num.group(0) if num else '?'} ({kind_})",
                                     "описание": A("; ".join(x for x in parts if x)), "ocr": scan})
    return {"items": items, "marks": None, "note": None if items else "в спецификации не распознано изделий"}

READERS = {"КП": kp, "опросный лист": oprosnyi, "теплотехнический расчёт": teplo,
           "техническое описание": to_doc, "смета": smeta, "спецификация окон": windows}

def build_docs(paths):
    """Пути к PDF → данные проекта для генератора: {label, date, items, docs}. None — ни один файл не дал позиций.
    Каждая позиция несёт свой источник («опросный лист от 09.10.2026») — он и попадает в ответ покупателю."""
    docs, items = [], []
    for p in paths:
        try:
            t, scan = text_or_ocr(p); k = kind(p, t)   # 21.10: скан — через распознавание
            if not k: docs.append({"file": p.split("/")[-1], "kind": None, "date": None, "items": 0,
                                   "note": "вид документа не распознан: ждали КП, опросный лист или теплотехнический расчёт"}); continue
            d = date_of(p); src = f"{k} от {d}" if d else k
            r = READERS[k](p) if k not in ("теплотехнический расчёт", "техническое описание", "смета", "спецификация окон") else \
                (teplo(p, t) if k == "теплотехнический расчёт" else READERS[k](p, None if scan else t))
            for n, i in enumerate(r["items"], 1):
                i["id"] = f"ОБ-{len(docs) + 1}-{n:02d}"; i["источник_метка"] = src; i["источник"] = f"данные проекта: {src}"
            items += r["items"]
            docs.append({"file": p.split("/")[-1], "kind": k, "date": d, "items": len(r["items"]), "note": r.get("note"), "ocr": scan})
        except Exception as e:
            docs.append({"file": p.split("/")[-1], "kind": None, "date": None, "items": 0, "note": f"не разобрано: {type(e).__name__}"})
    if not items: return None, docs
    srcs = "; ".join(dict.fromkeys(f"{d['kind']} от {d['date']}" if d["date"] else d["kind"] for d in docs if d["items"]))
    dates = [d["date"] for d in docs if d["items"] and d["date"]]
    obj = {"label": f"Данные Вашего проекта ({srcs})", "date": "; ".join(dict.fromkeys(dates)) or None,
           "sources": srcs, "items": items, "docs": docs}
    try: obj = BV.attach(obj)   # 28.10: базовая комплектация нужной редакции (по дате объекта) или вопрос сотруднику
    except Exception as e: obj["base"] = {"status": "сбой", "note": f"база не подключена: {type(e).__name__}"}
    return obj, docs

if __name__ == "__main__":
    obj, docs = build_docs(sys.argv[1:])
    for d in docs: print(f"{d['file']}: вид {d['kind']}, дата {d['date']}, позиций {d['items']}" + (f" — {d['note']}" if d.get("note") else ""))
    if obj:
        print(f"\nисточник: {obj['sources']}\nпозиций всего: {len(obj['items'])}")
        for i in obj["items"]: print(f"  [{i['id']}] ({i['источник_метка']}) {i['позиция']}: {i['описание']}")
        print("ПДн после обезличивания:", len(anonymize(json.dumps(obj['items'], ensure_ascii=False))[1]))
