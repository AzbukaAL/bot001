#!/usr/bin/env python3
"""СП 131.13330.2025 «Строительная климатология» — климатические таблицы по населённым пунктам (27.10.2026).

Таблицы 5.1 (холодный период), 6.1 (тёплый период) и 7.1 (средняя месячная температура) читаются ПОСТРОЧНО из PDF
заказчика (materials/normy/sp131-13330-2025.pdf, экспорт базы cntd). Второй экземпляр того же свода (SP_131.13330.2025.pdf,
сайт Минстроя) — независимая сверка: значения пункта считаются надёжными, только если обе копии дали одно и то же;
расхождения и пункты, найденные лишь в одной копии, — в отчёт build/climate_sp131_report.md, в JSON с пометкой.
Числа (расчётная температура, продолжительность и средняя температура отопительного периода) дальше берёт код
(src/calc_teplo.py), а не модель.

  python3 src/climate_sp131.py          → build/climate_sp131.json + отчёт
  from climate_sp131 import lookup      → lookup("Ростов-на-Дону") → {"region", "cold", "warm", "monthly", ...}
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = f"{ROOT}/materials/normy"
OUT = f"{ROOT}/build/climate_sp131.json"
REPORT = f"{ROOT}/build/climate_sp131_report.md"
DOC = "СП 131.13330.2025"
PRIMARY = "sp131-13330-2025.pdf"        # от заказчика 27.10.2026
CHECK = "SP_131.13330.2025.pdf"         # Минстрой, скачан 30.09.2026 — только для сверки

# графы таблицы 5.1 (холодный период) — в порядке столбцов; (ключ, подпись для текста)
COLD = [("t_cold_days_098", "температура воздуха наиболее холодных суток обеспеченностью 0,98, °C"),
        ("t_cold_days_092", "то же, обеспеченностью 0,92, °C"),
        ("t_5day_098", "температура воздуха наиболее холодной пятидневки обеспеченностью 0,98, °C"),
        ("t_5day_092", "то же, обеспеченностью 0,92, °C"),
        ("t_094", "температура воздуха обеспеченностью 0,94, °C"),
        ("t_abs_min", "абсолютная минимальная температура воздуха, °C"),
        ("amp_cold_month", "средняя суточная амплитуда температуры воздуха наиболее холодного месяца, °C"),
        ("z_le0", "продолжительность периода со средней суточной температурой воздуха ≤ 0 °C, сут"),
        ("t_le0", "средняя температура воздуха периода ≤ 0 °C, °C"),
        ("z_le8", "продолжительность периода со средней суточной температурой воздуха ≤ 8 °C, сут"),
        ("t_le8", "средняя температура воздуха периода ≤ 8 °C, °C"),
        ("z_le10", "продолжительность периода со средней суточной температурой воздуха ≤ 10 °C, сут"),
        ("t_le10", "средняя температура воздуха периода ≤ 10 °C, °C"),
        ("rh_cold_month", "средняя месячная относительная влажность воздуха наиболее холодного месяца, %"),
        ("rh_15h_cold_month", "средняя месячная относительная влажность воздуха в 15 ч наиболее холодного месяца, %"),
        ("precip_XI_III", "количество осадков за ноябрь — март, мм"),
        ("wind_dir_XII_II", "преобладающее направление ветра за декабрь — февраль"),
        ("wind_max_jan", "максимальная из средних скоростей ветра по румбам за январь, м/с"),
        ("wind_avg_le8", "средняя скорость ветра за период со средней суточной температурой воздуха ≤ 8 °C, м/с")]
# графы таблицы 6.1 (тёплый период)
WARM = [("pressure_hPa", "барометрическое давление, гПа"),
        ("t_095", "температура воздуха обеспеченностью 0,95, °C"),
        ("t_098", "температура воздуха обеспеченностью 0,98, °C"),
        ("t_max_avg_warm_month", "средняя максимальная температура воздуха наиболее тёплого месяца, °C"),
        ("t_abs_max", "абсолютная максимальная температура воздуха, °C"),
        ("amp_warm_month", "средняя суточная амплитуда температуры воздуха наиболее тёплого месяца, °C"),
        ("rh_warm_month", "средняя месячная относительная влажность воздуха наиболее тёплого месяца, %"),
        ("rh_15h_warm_month", "средняя месячная относительная влажность воздуха в 15 ч наиболее тёплого месяца, %"),
        ("precip_IV_X", "количество осадков за апрель — октябрь, мм"),
        ("precip_day_max", "суточный максимум осадков, мм"),
        ("wind_dir_VI_VIII", "преобладающее направление ветра за июнь — август"),
        ("wind_min_avg_jul", "минимальная из средних скоростей ветра по румбам за июль, м/с")]
MONTHS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "год"]
TABLES = {"5.1": ("cold", COLD), "6.1": ("warm", WARM), "7.1": ("monthly", [(m, m) for m in MONTHS])}

REGION = re.compile(r"(область|край|республика|округ|Москва|Санкт-Петербург|Севастополь|Чувашия|Югра)\b", re.I)
ROW = re.compile(r"^\s{0,4}([А-ЯЁа-яё][А-Яа-яёЁ.()\- ]*?[А-Яа-яёЁ.)\-])\s{2,}(-?\d.*)$")   # «о.Беринга», «Комсомольск-на-» (перенос)
DIR = r"(?:С|СВ|В|ЮВ|Ю|ЮЗ|З|СЗ)"
TOKEN = re.compile(rf"^(-?\d+(?:,\d+)?)\*?$|^({DIR}(?:, ?{DIR})?|-)\*?$")
TAB = r"Т\s?а\s?б\s?л\s?и\s?ц\s?а"

def _key(name):
    return re.sub(r"\s*([.\-])\s*", r"\1", name).lower().replace("ё", "е").replace(" ", "")

def pdf_text(p):
    return subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True).stdout

def _val(tok):
    """Ячейка → число (запятая → точка), направление ветра — строкой, «-» → None. Звёздочка сноски снимается."""
    m = TOKEN.match(tok)
    if not m: return "?"
    if m.group(1) is not None: return float(m.group(1).replace(",", ".")) if "," in m.group(1) else int(m.group(1))
    return None if m.group(2) == "-" else m.group(2)

def _cells(rest):
    """Хвост строки → значения граф. Латинская «C» в направлении ветра (копия Минстроя) → кириллица; «З, СЗ» — одна ячейка."""
    rest = re.sub(r"(?<![А-Яа-яA-Za-z])C(?=[ЗВ]?\b)", "С", rest)
    toks = re.sub(rf"\b({DIR}),\s+({DIR})\b", r"\1,\2", rest).split()
    return [_val(t) for t in toks], "*" in rest

def parse_table(text, num, cols):
    """Строки одной таблицы: {пункт: (регион, {графа: значение}, сноска)}. Строка принимается только при полном наборе
    граф — иначе в проблемы (молча не выдумываем). Перенос имени пункта: в копии заказчика продолжение идёт ПОСЛЕ строки
    чисел («Комсомольск-на-» … / «Амуре»), в копии Минстроя имя стоит на своей строке, а числа — на следующей
    («Петропавловск-» / «   -21 -19 …»); различаем по следующей строке."""
    a, b = num.split(".")
    start = re.search(rf"^\s*{TAB}\s*{a}\s?\.\s?{b}\b.*$", text, re.M)   # «Таблица 5.1» (заказчик) и «Т а б л и ц а 6 .1» (Минстрой)
    if not start: return {}, [f"таблица {num} не найдена"]
    nxt = re.search(rf"^\s*{TAB}\s*\d+\s?\.\s?\d+\b", text[start.end():], re.M)
    body = text[start.end():start.end() + nxt.start()] if nxt else text[start.end():]
    lines = [l.replace("\xa0", " ").rstrip() for l in body.split("\n")]
    lines = [l for l in lines if l.strip()]
    rows, problems, region, last, prefix = {}, [], None, None, None
    def add(name, rest):
        nonlocal last
        name = re.sub(r"\s+", " ", name).strip()
        vals, note = _cells(rest)
        if len(vals) != len(cols) or "?" in vals:
            if sum(v != "?" for v in vals) * 2 >= len(vals):   # шапка таблицы, попавшая под шаблон строки, — не проблема
                problems.append(f"табл. {num}, «{name}»: {len(vals)} значений вместо {len(cols)}: {rest.strip()[:90]}")
            last = None; return
        rows[name] = (region, dict(zip([c for c, _ in cols], vals)), note); last = name
    for k, line in enumerate(lines):
        s = line.strip(); peek = lines[k + 1].strip() if k + 1 < len(lines) else ""
        if re.fullmatch(r"\d{1,3}", s) or s.startswith("*") or s.startswith("_") or "Примечание изготовителя" in s: last = None; continue
        if not re.search(r"\d", s) and REGION.search(s) and not line.startswith(" " * 6):
            region = re.sub(r"\s+", " ", s); last = prefix = None; continue
        m = ROW.match(line)
        if m: add((prefix + " " + m.group(1)) if prefix else m.group(1), m.group(2)); prefix = None; continue
        if prefix and re.match(r"^\s+-?\d", line): add(prefix, line); prefix = None; continue
        short = not re.search(r"\d", s) and len(s) <= 26 and len(s.split()) <= 2
        if short and re.match(r"^\s*-?\d", peek) and len(peek.split()) >= 3:        # имя на своей строке, числа ниже (Минстрой); «57» — номер страницы
            prefix = s; last = None; continue
        if short and last and not line.startswith(" "):                                 # продолжение имени после строки чисел (заказчик)
            full = (last + s) if last.endswith("-") or len(s) <= 2 else (last + " " + s)   # «Сахалински» + «й»
            rows[full] = rows.pop(last); last = None; continue
        last = prefix = None
    return rows, problems

def build():
    prim = pdf_text(f"{N}/{PRIMARY}"); chk = pdf_text(f"{N}/{CHECK}")
    data, report = {}, [f"# {DOC}: климатические таблицы по пунктам", "",
                        f"Источник: `{PRIMARY}` (от заказчика 27.10.2026); сверка: `{CHECK}` (Минстрой).", ""]
    for num, (key, cols) in TABLES.items():
        rp, pp = parse_table(prim, num, cols); rc, pc = parse_table(chk, num, cols)
        same = diff = only_p = 0
        rck = {_key(n): v for n, v in rc.items()}
        for name, (region, vals, note) in rp.items():
            d = data.setdefault(name, {"region": region, "notes": []})
            d[key] = vals
            c = rck.get(_key(name))
            if c is None:
                only_p += 1; d["notes"].append(f"табл. {num}: нет в копии Минстроя — не сверено")
            elif c[1] != vals:
                diff += 1; bad = [k for k in vals if vals[k] != c[1][k]]
                d["notes"].append(f"табл. {num}: расходится с копией Минстроя по графам {bad} — сверить с бумажным изданием")
                report.append(f"- ⚠ табл. {num}, {name} ({region}): заказчик {[vals[k] for k in bad]} ≠ Минстрой {[c[1][k] for k in bad]} ({bad})")
            else: same += 1
            if note: d["notes"].append(f"табл. {num}: в копии заказчика у значений сноска «*» (примечание базы cntd)")
        only_c = [n for n in rc if _key(n) not in {_key(x) for x in rp}]
        report.append(f"- таблица {num}: пунктов у заказчика {len(rp)}, сошлось с Минстроем {same}, расхождений {diff}, "
                      f"только у заказчика {only_p}, только у Минстроя {len(only_c)}{': ' + ', '.join(only_c[:8]) if only_c else ''}")
        for p in pp: report.append(f"  - не разобрано (заказчик): {p}")
        for p in pc: report.append(f"  - не разобрано (Минстрой): {p}")
    for d in data.values():
        d["source"] = f"{DOC}, таблицы " + ", ".join(n for n, (k, _) in TABLES.items() if k in d)
        d["checked"] = not any("расходится" in n or "не сверено" in n for n in d["notes"])
    # одно имя в нескольких регионах — пункт без региона неоднозначен
    report.append(f"\nИтого пунктов: {len(data)}; сверены полностью: {sum(d['checked'] for d in data.values())}.")
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(REPORT, "w", encoding="utf-8").write("\n".join(report) + "\n")
    return data, report

def fmt(v):
    if v is None: return "нет данных"
    if isinstance(v, float): return f"{v:.1f}".replace(".", ",")
    return str(v)

def point_text(name, d):
    """Строка пункта для индекса норм — те же числа словами, чтобы цитата сверялась дословно с индексом."""
    parts = [f"{name} ({d.get('region') or 'регион не указан'}). Таблица 5.1 — холодный период:"]
    c = d.get("cold") or {}
    for k, label in COLD:
        if k in c: parts.append(f"{label} — {fmt(c[k])};")
    w = d.get("warm") or {}
    if w:
        parts.append("Таблица 6.1 — тёплый период:")
        for k, label in WARM:
            if k in w: parts.append(f"{label} — {fmt(w[k])};")
    m = d.get("monthly") or {}
    if m: parts.append("Таблица 7.1 — средняя месячная и годовая температура воздуха, °C: " +
                       ", ".join(f"{mm} — {fmt(m[mm])}" for mm in MONTHS if mm in m) + ".")
    return " ".join(parts)

_DATA = None
def data():
    global _DATA
    if _DATA is None: _DATA = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    return _DATA

def lookup(name):
    """Пункт по имени (регистр и «ё» не важны). Нет в таблице → None — пусть код скажет об этом явно, а не модель."""
    if not name: return None
    key = name.strip().lower().replace("ё", "е")
    for k, v in data().items():
        if k.lower().replace("ё", "е") == key: return {"name": k, **v}
    return None

if __name__ == "__main__":
    d, rep = build()
    print("\n".join(rep))
    for n in ("Ростов-на-Дону", "Миллерово", "Луганск"):
        x = lookup(n); c = x["cold"]
        print(f"{n}: пятидневка 0,92 = {c['t_5day_092']} °C, период ≤8 °C: {c['z_le8']} сут, {c['t_le8']} °C; сверено: {x['checked']}")
