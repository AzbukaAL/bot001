"""Текст PDF, свёрстанного в две колонки (СП 31-105-2002 от заказчика, 08.10.2026). По страницам: левая половина, затем правая
(pdfplumber, рамка — page.bbox). Перед извлечением выбрасывается текст внутри рисунков и таблиц: это области, где сгущаются
векторные линии/прямоугольники/кривые. Иначе надписи на рисунках и ячейки таблиц вклинивались в пункты
(6.2.8.2 «…Каменная кладка или бетон…», 7.2.5 «пре д дусматриваться», 7.3.5.2 «винТ а б л и ц а»). Номера таблиц и рисунков в тексте
пунктов остаются ссылками; содержимое таблиц в индекс не попадает. Мягкий перенос (U+00AD) склеивается; колонтитулы и подписи
«Рисунок N…» отбрасываются."""
import re
import pdfplumber
HEAD = re.compile(r"^\s*(СП 31-105-2002|СП 31 -1 0 5 -2 0 0 2|\d{1,3})\s*$")
CAP = re.compile(r"^\s*(Рисунок|Т а б л и ц а|Таблица)\s+[\dА-Я]")

def regions(pg, gap=6, min_area=1500):
    """Области рисунков/таблиц: слить близкие графические объекты, оставить крупные."""
    boxes = [[o["x0"], o["top"], o["x1"], o["bottom"]] for o in pg.lines + pg.rects + pg.curves]
    merged = True
    while merged:
        merged = False; out = []
        for b in boxes:
            for m in out:
                if b[0] - gap <= m[2] and m[0] - gap <= b[2] and b[1] - gap <= m[3] and m[1] - gap <= b[3]:
                    m[0], m[1], m[2], m[3] = min(m[0], b[0]), min(m[1], b[1]), max(m[2], b[2]), max(m[3], b[3]); merged = True; break
            else: out.append(list(b))
        boxes = out
    return [b for b in boxes if (b[2] - b[0]) * (b[3] - b[1]) >= min_area]

def gap_x(pg, lo=0.35, hi=0.65, min_gap=4):
    """Середина самой широкой вертикальной полосы без символов в средней части страницы; None — полосы нет
    (её пересекает широкий заголовок/таблица)."""
    x0, _, x1, _ = pg.bbox; W = x1 - x0; a, b = x0 + W * lo, x0 + W * hi
    cov = sorted((c["x0"], c["x1"]) for c in pg.chars if c["x1"] > a and c["x0"] < b and c.get("text", "").strip())
    best, prev = (0, None), a
    for c0, c1 in cov:
        if c0 - prev > best[0]: best = (c0 - prev, (prev + c0) / 2)
        prev = max(prev, c1)
    if b - prev > best[0]: best = (b - prev, (prev + b) / 2)
    return best[1] if best[0] >= min_gap else None

def starts_x(pg, lo=0.4, hi=0.7, min_lines=5):
    """Левый край правой колонки: наименьшая позиция x в правой части, с которой начинается ≥ min_lines строк (−1 pt)."""
    import collections
    x0, _, x1, _ = pg.bbox; W = x1 - x0
    lines = collections.defaultdict(list)
    for w in pg.extract_words(): lines[round(w["top"])].append(w["x0"])
    starts = collections.Counter()
    for xs in lines.values():
        right = [x for x in xs if x0 + W * lo <= x <= x0 + W * hi]
        if right: starts[round(min(right))] += 1
    cand = sorted(x for x, n in starts.items() if n >= min_lines)
    return cand[0] - 1 if cand else None

def gutter_x(pg):
    """Граница колонок. Колонки несимметричны (стр. 25: левая до x≈255, правая с x≈275 при середине 276): при резке посередине
    первая буква строки правой колонки уходила в левую («пре д дусматриваться» в 7.2.5). Сначала пустая полоса, иначе — левый край
    правой колонки, иначе — середина."""
    x0, _, x1, _ = pg.bbox
    return gap_x(pg) or starts_x(pg) or x0 + (x1 - x0) / 2

def pdf_text_columns(p):
    out = []
    with pdfplumber.open(p) as pdf:
        for pg in pdf.pages:
            R = regions(pg)
            inside = lambda o: any(r[0] - 2 <= (o["x0"] + o["x1"]) / 2 <= r[2] + 2 and r[1] - 2 <= (o["top"] + o["bottom"]) / 2 <= r[3] + 2 for r in R)
            body = pg.filter(lambda o: o.get("object_type") != "char" or not inside(o))
            x0, y0, x1, y1 = pg.bbox; xm = gutter_x(pg)
            for box in ((x0, y0, xm, y1), (xm, y0, x1, y1)):
                for line in (body.crop(box).extract_text() or "").split("\n"):
                    if HEAD.match(line) or CAP.match(line): continue
                    out.append(line)
    return re.sub(r"­\s*\n\s*", "", "\n".join(out)).replace("­", "")

if __name__ == "__main__":
    import sys; sys.path.insert(0, "/opt/captain-sam/src"); import normy_parse as NP
    secs, pts = NP.parse(pdf_text_columns("/opt/captain-sam/materials/normy/sp31-105-2002-full.pdf"))
    print("разделов", len(secs), "пунктов", len(pts))
    for k in ["4.2.1", "4.2.3", "4.4.1", "6.2.8.2", "6.2.8.4", "7.2.5", "7.3.5.2", "8.2.1.2", "8.2.2.6", "8.2.3.5"]:
        v = pts.get(k); print(f"\n[{k}] раздел {v['section'] if v else '—'}:", (v["text"][:380] if v else "НЕТ ПУНКТА"))
