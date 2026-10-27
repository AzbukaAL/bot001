"""Теплотехника — кодом, не моделью (27.10.2026, план до акта, п. 5 «сопротивление теплопередаче»).
- ГСОП по формуле (5.2) СП 50.13330.2024 на данных таблицы 5.1 СП 131.13330.2025 (src/climate_sp131.py): период со средней
  суточной температурой ≤ 8 °C (жилые здания);
- базовые требуемые сопротивления теплопередаче R_тр по таблице 3 СП 50 (поз. 1.1 — жилые): R = a·ГСОП + b, графа «окна» —
  линейная интерполяция между строками таблицы. Строки и коэффициенты читаются из текста СП 50 (кэш build/sp50_table3.json);
- t_в = 20 °C — минимальная оптимальная температура жилых помещений по ГОСТ 30494: текста ГОСТ в материалах нет, константа с пометкой.
Фактическое R ограждений НЕ считается: теплопроводность утеплителя заказчика (минеральная вата ≈ 12 кг/м³ по стандарту компании)
в загруженных текстах отсутствует (прил. М СП 50 — изделия от 25 кг/м³) — вопрос заказчику, а не допущение модели.
Числа округляются: ГСОП — до 1 °C·сут, R — до 0,01 м²·°C/Вт.
"""
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import climate_sp131 as CL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SP50 = f"{ROOT}/materials/normy/SP_50.13330.2024.pdf"
CACHE = f"{ROOT}/build/sp50_table3.json"
T_IN = 20   # °C, ГОСТ 30494 — минимальная оптимальная температура жилых помещений (холодный период); текст ГОСТ не загружен
T_IN_NOTE = "t_в = 20 °C — минимальная оптимальная температура жилых помещений по ГОСТ 30494 (текст ГОСТ в материалах не загружен)"
TOPIC = re.compile(r"утепл|теплопотер|теплопередач|ГСОП|градусо-сут|энергоэффект|теплов\w+ защит|промерз|тепл\w* контур", re.I)
NO_LAMBDA = ("Фактическое сопротивление теплопередаче ограждений объекта не рассчитано: расчётная теплопроводность утеплителя "
             "(минеральная вата плотностью около 12 кг/м³ по стандарту компании) в загруженных текстах норм отсутствует.")
COLS = ["стены", "покрытия", "перекрытия чердачные и полы над подпольем", "окна", "фонари"]

def fmt(x, nd=2):
    return f"{x:.{nd}f}".replace(".", ",")

def _num(t):
    return None if t in ("–", "-", "—") else float(t.replace(",", "."))

def table3():
    """Таблица 3 СП 50.13330.2024, поз. 1.1 (жилые): {"rows": [[ГСОП, стены, покрытия, перекрытия, окна, фонари], …], "a": [...], "b": [...]}.
    Из текста PDF; разобранное кэшируется. Не нашли строки — исключение: без коэффициентов считать нельзя."""
    if os.path.exists(CACHE): return json.load(open(CACHE, encoding="utf-8"))
    text = subprocess.run(["pdftotext", "-layout", SP50, "-"], capture_output=True, text=True).stdout
    m = re.search(r"^\s*Таблица 3\s*$", text, re.M)
    body = text[m.end():] if m else ""
    i = body.find("1.1 Жилые"); j = body.find("1.2 ", i)
    block = body[i:j] if i >= 0 and j > i else ""
    rows, ab = [], {}
    for line in block.split("\n"):
        r = re.search(r"(\d{4,5})\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$", line)
        if r: rows.append([float(r.group(1))] + [_num(r.group(k)) for k in range(2, 7)]); continue
        r = re.match(r"^\s*([ab])\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$", line)
        if r: ab[r.group(1)] = [_num(r.group(k)) for k in range(2, 7)]
    if len(rows) < 5 or "a" not in ab or "b" not in ab:
        raise RuntimeError(f"таблица 3 СП 50 не разобрана: строк {len(rows)}, коэффициенты {sorted(ab)}")
    t3 = {"rows": rows, "a": ab["a"], "b": ab["b"], "source": "СП 50.13330.2024, таблица 3, поз. 1.1"}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(t3, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return t3

def gsop(t_ot, z_ot, t_in=T_IN):
    """Формула (5.2) СП 50: ГСОП = (t_в − t_от)·z_от."""
    return (t_in - t_ot) * z_ot

def r_req(g):
    """Базовые требуемые R по таблице 3 (поз. 1.1): R = a·ГСОП + b; окна (графа 6, a и b не заданы) — интерполяция между строками."""
    t3 = table3(); out = {}
    for k, name in enumerate(COLS):
        a, b = t3["a"][k], t3["b"][k]
        if a is not None and b is not None:
            out[name] = {"value": a * g + b, "how": f"{fmt(a, 5 if a < 0.0001 else 5).rstrip('0')}·{fmt(g, 0)} + {fmt(b, 1)}"}
            continue
        pts = [(r[0], r[k + 1]) for r in t3["rows"] if r[k + 1] is not None]
        lo = max((p for p in pts if p[0] <= g), default=pts[0]); hi = min((p for p in pts if p[0] >= g), default=pts[-1])
        v = lo[1] if hi[0] == lo[0] else lo[1] + (g - lo[0]) * (hi[1] - lo[1]) / (hi[0] - lo[0])
        out[name] = {"value": v, "how": f"интерполяция между {fmt(lo[0], 0)} ({fmt(lo[1])}) и {fmt(hi[0], 0)} ({fmt(hi[1])}) °C·сут"}
    return out

def _item(obj, rx):
    return next((str(i.get("описание") or "") for i in (obj or {}).get("items") or [] if re.search(rx, str(i.get("позиция") or ""), re.I)), "")

def from_project(obj, claim):
    """Строки расчёта по ДАННЫМ ПРОЕКТА: город — из теплотехнического расчёта (project_docs.TEPLO). Тема не теплотехническая
    или города нет — []. Город не найден в таблице — об этом явная строка (факт для ответа), а не тишина."""
    if not obj or not TOPIC.search(claim or ""): return []
    city = _item(obj, r"^Город")
    if not city: return []
    p = CL.lookup(city)
    if not p or not p.get("cold"):
        return [f"Место строительства по теплотехническому расчёту объекта — {city}: в таблице 5.1 СП 131.13330.2025 такого пункта нет, "
                "климатические параметры для расчёта не определены."]
    c = p["cold"]; t5, z, t = c["t_5day_092"], c["z_le8"], c["t_le8"]
    L = [f"Место строительства по теплотехническому расчёту объекта — {p['name']}. СП 131.13330.2025, таблица 5.1 ({p['region']}): "
         f"температура воздуха наиболее холодной пятидневки обеспеченностью 0,92 — {CL.fmt(t5)} °C (расчётная температура для "
         f"отопления — параметры Б холодного периода, таблица 16.1); отопительный период (среднесуточная температура ≤ 8 °C) — "
         f"{CL.fmt(z)} сут, средняя температура {CL.fmt(t)} °C."
         + ("" if p.get("checked") else " Строка таблицы не сверена со второй копией свода — проверить по изданию.")]
    tr = _item(obj, r"^Расчётная температура")
    if re.search(r"-?\d+", tr):
        tr_v = int(re.search(r"-?\d+", tr).group(0))
        L.append(f"Расчётная температура наружного воздуха в теплотехническом расчёте объекта {tr_v} °C "
                 + ("совпадает" if tr_v == t5 else f"НЕ совпадает (в таблице {CL.fmt(t5)} °C)") + " с таблицей 5.1 СП 131.13330.2025.")
    g = gsop(t, z)
    L.append(f"ГСОП = (t_в − t_от)·z_от = ({T_IN} − ({CL.fmt(t)}))·{CL.fmt(z)} = {fmt(g, 0)} °C·сут (СП 50.13330.2024, формула 5.2; {T_IN_NOTE}).")
    R = r_req(g)
    L.append("Базовые требуемые сопротивления теплопередаче по таблице 3 СП 50.13330.2024 (поз. 1.1, жилые; R = a·ГСОП + b), м²·°C/Вт: "
             + "; ".join(f"{n} — {R[n]['how']} = {fmt(R[n]['value'])}" for n in COLS[:4]) + ".")
    L.append(NO_LAMBDA)
    return L

if __name__ == "__main__":
    t3 = table3()
    assert t3["a"][:3] == [0.00035, 0.0005, 0.00045] and t3["b"][:3] == [1.4, 2.2, 1.9], t3
    assert [r[0] for r in t3["rows"]] == [1000, 2000, 4000, 6000, 8000, 10000, 12000] and t3["rows"][2][4] == 0.63
    OBJ = {"items": [{"позиция": "Город (место строительства)", "описание": "Луганск"},
                     {"позиция": "Расчётная температура наружного воздуха, °C", "описание": "-23"}]}
    for l in from_project(OBJ, "утепление стен 150 мм недостаточно"): print(l)
    g = gsop(0.1, 173); assert fmt(g, 0) == "3443" and fmt(r_req(g)["стены"]["value"]) == "2,60" and fmt(r_req(g)["окна"]["value"]) == "0,59"
    assert from_project(OBJ, "почему сайдинг виниловый") == [] and from_project(None, "утепление") == []
    print("проверки: ок")
