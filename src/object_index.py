"""Индекс данных объекта из КП (шаблон КП заказчика: таблица «раздел / описание / цена», строки групп с суммой группы).
Источник «данные объекта <имя>» — отдельно от норм (normy_index.json) и стандарта компании (reglament_index.json).
Всё текстовое — через обезличиватель (в КП имена покупателей). Цены — как в КП; суммы групп сверяются кодом.
07.10.2026: первый объект — «Тест 1», Киржач (materials/objects/test1-kp.pdf). В поиск системы пока не подключён.
07.10.2026: «Тест 1» прислан по ошибке — ЗАМОРОЖЕН. Файл <pdf>.FROZEN.md рядом с КП = индекс не строить.

  python3 src/object_index.py materials/objects/test1-kp.pdf "Тест 1" build/object_test1_index.json
"""
import os
import json, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
from anonymize import anonymize
import pdfplumber

MONEY = re.compile(r"(\d{1,3}(?: \d{3})*,\d{2}) ₽")
# Раздел конструктива по названию строки КП (первое совпадение)
SECTIONS = [("фундамент", r"фундамент|свай"), ("обвязка", r"обвязоч"), ("кровля", r"кровл|кровел|стропил|снего|водосточ"),
            ("перекрытия", r"перекрыти|высота потолк"), ("террасы", r"террас"), ("окна/двери", r"окна|двери"),
            ("стены", r"наружные стены|утепления наружных стен|вентиляция фасада|внутренние перегородки"),
            ("инженерка", r"электри|водоснаб|септик|отоплен|вентиляц|теплый пол"),
            ("отделка", r"отделк|половое|подшивк|обрешётка|лестниц|шумоизол|обработк|сайдинг")]

def A(t): return anonymize(" ".join((t or "").split()))[0]
def rub(s): return float(s.replace(" ", "").replace(",", ".")) if s else None
def section(label):
    for name, rx in SECTIONS:
        if re.search(rx, label, re.I): return name
    return "прочее"

def kp_date(pdf):
    """Дата КП — из метаданных PDF (CreationDate), иначе None."""
    info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    m = re.search(r"CreationDate:\s+\w+\s+(\w+)\s+(\d+)\s+[\d:]+\s+(\d{4})", info)
    MON = dict(Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6, Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12)
    return f"{int(m.group(2)):02d}.{MON.get(m.group(1), 0):02d}.{m.group(3)}" if m else None

def build(PDF, NAME):
    """КП (PDF по шаблону заказчика) → {meta, groups, items}; всё текстовое — обезличено. 09.10: функция для бота."""
    import os
    if os.path.exists(PDF + ".FROZEN.md"): sys.exit(f"ЗАМОРОЖЕНО: {PDF}.FROZEN.md — индекс не строится, см. файл-пометку")
    SOURCE = f"данные объекта {NAME}"
    text = subprocess.run(["pdftotext", "-layout", PDF, "-"], capture_output=True, text=True, check=True).stdout
    flat = A(text)
    meta = {"объект": NAME, "источник": SOURCE, "файл": PDF.split("/")[-1]}
    for key, rx in [("населённый пункт", r"Адрес обьекта\s+(\S+)"), ("площадь застройки", r"Площадь застройки\s+([\d,.]+ м2)"),
                    ("класс энергоэффективности", r"классу\s+([А-ЯA-Z]\+*)\s"), ("размер", r"(\d+х\d+)")]:
        m = re.search(rx, flat)
        if m and m.lastindex: meta[key] = m.group(1)

    items, groups, group = [], [], None
    with pdfplumber.open(PDF) as pdf:
        for pno, pg in enumerate(pdf.pages, 1):
            for t in pg.extract_tables():
                for label, desc, price in (r + [None] * (3 - len(r)) for r in t):
                    label, desc, price = A(label), A(desc), A(price)
                    if not desc and not price:
                        m = MONEY.findall(label)
                        head = MONEY.sub("", label).strip()
                        if m and head and not head.startswith(("Логистика", "Итоговая")):
                            group = {"группа": head, "сумма": rub(m[0]), "страница": pno}; groups.append(group)
                        elif head.startswith("Логистика"):
                            for nm, val in re.findall(r"(\w+) (\d{1,3}(?: \d{3})*,\d{2}) ₽", label):
                                items.append({"группа": "Накладные расходы", "раздел": "прочее", "позиция": nm, "описание": "",
                                              "цена": rub(val), "страница": pno})
                        continue
                    if not group: continue
                    items.append({"группа": group["группа"], "раздел": section(label), "позиция": label, "описание": desc.lstrip("- ").strip(),
                                  "цена": rub(MONEY.search(price).group(1)) if MONEY.search(price) else None,
                                  "пометки_КД": sorted(set(re.findall(r"\((К|Д)\)", desc))), "страница": pno})

    # Цена стоит одной строкой на всю группу (напр. «Тёплый контур» — у обвязки): помечаем, чтобы не читать её как цену позиции
    for g in groups:
        gi = [i for i in items if i["группа"] == g["группа"]]; priced = [i for i in gi if i["цена"]]
        for i in gi:
            i["цена_относится_к"] = "группе" if len(gi) > 1 and len(priced) == 1 and i is priced[0] and i["цена"] == g["сумма"] else (
                "позиции" if i["цена"] else "не указана")

    total = rub(MONEY.findall(flat)[-1]) if MONEY.findall(flat) else None
    check = []
    for g in groups:
        s = sum(i["цена"] or 0 for i in items if i["группа"] == g["группа"])
        check.append({"группа": g["группа"], "сумма_в_КП": g["сумма"], "сумма_позиций": round(s, 2), "сходится": abs(s - g["сумма"]) < 0.01})
    meta["итог_в_КП"] = total
    meta["итог_сходится_с_группами"] = total is not None and abs(sum(g["сумма"] for g in groups) - total) < 0.01
    for n, i in enumerate(items, 1): i["id"] = f"ОБ-{NAME.replace(' ', '')}-{n:02d}"; i["источник"] = SOURCE
    meta["дата_КП"] = kp_date(PDF)
    return {"meta": meta, "groups": check, "items": items}

if __name__ == "__main__":
    PDF, NAME, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
    d = build(PDF, NAME); items, check, meta = d["items"], d["groups"], d["meta"]
    json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    left = anonymize(json.dumps(items, ensure_ascii=False))[1]
    print(f"позиций: {len(items)}, групп: {len(check)}, групп сходится: {sum(c['сходится'] for c in check)}/{len(check)}, "
          f"итог сходится: {meta['итог_сходится_с_группами']}, ПДн после обезличивания: {len(left)}")
