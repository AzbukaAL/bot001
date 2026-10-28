"""Версии базовых комплектаций заказчика (28.10.2026, решение Вадима).
База хранится снимками сайта с датой: materials/reglament/bazovye-komplektacii-ГГГГММДД/txt/<модель>.txt (tools/base_snapshot.py).
Ключ версии — строка «Дата:» в самом блоке (редакция у заказчика); дата снимка — вторичная. Реестр build/base_versions.json:
модель → редакции (без повторов по md5 блока). Для разбора берётся редакция с датой не позже даты объекта (КП, иначе самый
ранний документ проекта); нет модели, даты или подходящей редакции — текущая база НЕ подставляется, сотруднику уходит вопрос.
Техническое описание из договора — выше сайта: если оно в данных проекта, база сайта не подключается.
"""
import datetime, glob, hashlib, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_GLOB = f"{ROOT}/materials/reglament/bazovye-komplektacii-*"
REG = f"{ROOT}/build/base_versions.json"
SIZE = re.compile(r"(?<=\d)\s*[хxХX×*]\s*(?=\d)")
NOISE_TITLE = re.compile(r"^(?:Каркасн\w+ (?:дом|бан\w)\s+)|(?:\s*:|\s+(?:под ключ|[—–-])).*$")

def norm(s):
    """Ключ модели: «Барн-хаус 6 х 10», «Барн-хаус 6х10», «барнхаус 6×10» → «барн-хаус 6 х 10»."""
    s = " ".join(str(s or "").lower().replace("ё", "е").split())
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)
    s = SIZE.sub(" х ", s)
    return s.replace("барнхаус", "барн-хаус").strip()

def model_of(title):
    """Название модели из заголовка страницы: «Каркасный дом Солнечный ++ 6 х 9 под ключ в …» → «Солнечный ++ 6 х 9»."""
    t = NOISE_TITLE.sub("", " ".join(title.split()))
    return NOISE_TITLE.sub("", t).strip()

def iso(d):
    """«14.11.24», «17.12.2025», «от 30.09.2024» → «2024-11-14»; иначе None."""
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", d or "")
    if not m: return None
    y = int(m.group(3)); y = y + 2000 if y < 100 else y
    try: return datetime.date(y, int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError: return None

def ru(d):
    return f"{d[8:10]}.{d[5:7]}.{d[0:4]}" if d else "—"

def parse_txt(path):
    """Файл снимка → {model, url, fetched, edition, md5, rows}. Редакция — «Дата:» или «от ДД.ММ.ГГГГ» в заголовке блока."""
    t = open(path, encoding="utf-8").read()
    head, _, block = t.partition("\n\n")
    g = lambda k: (re.search(rf"^{k}: (.*)$", head, re.M) or [None, ""])[1].strip()
    lines = [l.strip() for l in block.strip().split("\n")]
    k = lines.index("Элемент Дома") if "Элемент Дома" in lines else 0
    ed = re.search(r"Дата:\s*([\d.]+)|от\s+(\d\d\.\d\d\.\d{4})", "\n".join(lines[:k + 1]))
    rows, i = [], k + 2   # после «Элемент Дома», «Описание Элемента Дома»
    while i + 1 < len(lines):
        rows.append((lines[i], lines[i + 1])); i += 2
    return {"model": model_of(g("Заголовок страницы")), "url": g("Источник"), "fetched": g("Загружено"),
            "edition": iso((ed.group(1) or ed.group(2)) if ed else None), "md5": hashlib.md5(block.strip().encode()).hexdigest()[:10],
            "rows": rows, "file": path}

def snapshot_date(folder):
    m = re.search(r"(\d{4})(\d{2})(\d{2})$", folder.rstrip("/"))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None

def build_registry(snap_glob=None, out=None):
    """Все снимки → реестр: {models: {ключ: {name, versions: [{edition, snapshot, fetched, md5, file, url}]}}}.
    Один и тот же блок (md5) в нескольких снимках — одна версия, с датой первого снимка, где он появился."""
    models = {}
    for folder in sorted(glob.glob(snap_glob or SNAP_GLOB)):
        sd = snapshot_date(folder)
        for f in sorted(glob.glob(f"{folder}/txt/*.txt")):
            p = parse_txt(f); key = norm(p["model"])
            m = models.setdefault(key, {"name": p["model"], "versions": []})
            if any(v["md5"] == p["md5"] for v in m["versions"]): continue
            m["versions"].append({"edition": p["edition"], "snapshot": sd, "fetched": p["fetched"], "md5": p["md5"],
                                  "file": os.path.relpath(f, ROOT), "url": p["url"]})
    for m in models.values(): m["versions"].sort(key=lambda v: (v["edition"] or "", v["snapshot"] or ""))
    reg = {"built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "models": models}
    out = out or REG
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(reg, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return reg

def registry(refresh=False):
    """Реестр из файла; пересобирается, если файла нет или снимки новее него."""
    if not refresh and os.path.exists(REG):
        folders = glob.glob(SNAP_GLOB)
        if not folders or os.path.getmtime(REG) >= max(os.path.getmtime(f) for f in folders):
            return json.load(open(REG, encoding="utf-8"))
    return build_registry()

def edition_for(model_key, obj_date, reg=None):
    """Редакция с датой не позже даты объекта — последняя из таких. Редакции без даты в выборе не участвуют. Нет — None."""
    m = (reg or registry())["models"].get(norm(model_key))
    if not m or not obj_date: return None
    ok = [v for v in m["versions"] if v["edition"] and v["edition"] <= obj_date]
    return max(ok, key=lambda v: v["edition"]) if ok else None

def model_from(obj, reg=None):
    """Модель дома по данным проекта: серия и размер в позициях («дома серии «Барн-хаус 2эт.», размер 6х10»). None — не найдена."""
    models = (reg or registry())["models"]
    text = norm(" ".join(f"{i.get('позиция') or ''} {i.get('описание') or ''}" for i in (obj or {}).get("items") or []))
    series = sorted({re.sub(r"\s+\d.*$", "", k) for k in models}, key=len, reverse=True)
    for s in series:
        m = re.search(re.escape(s) + r".{0,40}?(?<!\d)(\d+(?:\.\d+)? х \d+(?:\.\d+)?)(?!\d)", text)
        if m and f"{s} {m.group(1)}" in models: return f"{s} {m.group(1)}"
    return None

def obj_date(obj):
    """Дата объекта: дата КП, иначе самая ранняя дата документа с позициями. ISO или None."""
    docs = [d for d in (obj or {}).get("docs") or [] if d.get("items") and d.get("date")]
    kp = [d for d in docs if d.get("kind") == "КП"]
    ds = [iso(d["date"]) for d in (kp or docs)]
    return min([d for d in ds if d], default=None)

def attach(obj, reg=None):
    """Данные проекта → + позиции базовой комплектации нужной редакции (obj["base"]: status ok) либо вопрос сотруднику
    (status «не определена», question). ТО из договора в данных проекта — база сайта не подключается (status «ТО»)."""
    if not obj: return obj
    if any(d.get("kind") == "техническое описание" and d.get("items") for d in obj.get("docs") or []):
        obj["base"] = {"status": "ТО", "note": "техническое описание из договора в данных проекта — базовая комплектация сайта не используется"}
        return obj
    reg = reg or registry()
    model, date = model_from(obj, reg), obj_date(obj)
    q = None
    if not model: q = "модель дома по данным проекта не определена — по какой базовой комплектации (серия, размер, редакция) строился дом?"
    elif not date: q = f"дата КП/договора по данным проекта не определена — по какой редакции базовой комплектации «{reg['models'][model]['name']}» строился дом (дата договора)?"
    else:
        v = edition_for(model, date, reg)
        if not v:
            have = ", ".join(ru(x["edition"]) for x in reg["models"][model]["versions"] if x["edition"]) or "без даты"
            q = (f"для «{reg['models'][model]['name']}» нет редакции базовой комплектации с датой не позже {ru(date)} "
                 f"(в снимках редакции: {have}) — по какой базе строился дом?")
    if q:
        obj["base"] = {"status": "не определена", "model": model, "date": date, "question": q}
        return obj
    p = parse_txt(f"{ROOT}/{v['file']}")
    label = f"базовая комплектация «{reg['models'][model]['name']}», ред. {ru(v['edition'])}, снимок сайта {ru(v['snapshot'])}"
    n0 = len(obj["items"])
    for n, (el, desc) in enumerate(p["rows"], 1):
        obj["items"].append({"id": f"ОБ-БК-{n:02d}", "позиция": el, "описание": desc, "источник_метка": label,
                             "источник": f"данные проекта: {label}"})
    obj["sources"] = f"{obj['sources']}; {label}"; obj["label"] = f"Данные Вашего проекта ({obj['sources']})"
    obj["base"] = {"status": "ok", "model": model, "date": date, "edition": v["edition"], "snapshot": v["snapshot"],
                   "label": label, "items": len(obj["items"]) - n0}
    return obj

if __name__ == "__main__":
    reg = build_registry()
    print(f"моделей {len(reg['models'])}, редакций {sum(len(m['versions']) for m in reg['models'].values())} → {REG}")
    for k, m in sorted(reg["models"].items()):
        print(f"  {m['name']}: " + "; ".join(f"{ru(v['edition'])} (снимок {ru(v['snapshot'])}, {v['md5']})" for v in m["versions"]))
