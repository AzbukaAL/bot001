"""Эталон приёмки: пары «претензия → ответ Алексея» + вердикт Алексея (один из пяти типов).

Тексты претензий и ответов вырезает КОД из исходников (proverka-kamenskoe.docx по цветовым слоям,
pary-voprosy-otvety.md по разметке). Вердикты — разметка Claude по ответам Алексея, прогон №1, 30.09.2026;
ТРЕБУЕТ ПОДТВЕРЖДЕНИЯ Вадимом/Алексеем. Спорные — с полем disputed.

Типы: 1 подтверждается нормативом · 2 опровергается нормативом/регламентом/практикой · 3 встречный вопрос ·
      4 вне зоны ответственности · 5 основания не найдено.
"""
import json, re, sys
sys.path.insert(0, "/opt/captain-sam/src")

B = json.load(open("/opt/captain-sam/build/kamenskoe_blocks.json", encoding="utf-8"))

# block → (вердикт, нужен ли полный СП 31-105 по ответу Алексея, cut-маркер собственного чёрного текста Алексея, пометки)
K = [
    (20, 2, True,  None, "анкеровка обвязки к сваям: болты ≥12 мм, шаг ≤2,4 м, заделка ≥100 мм (СП 31-105 п. 6.2.8.x)"),
    (21, 2, True,  None, "крепёж плит: п. 7.3.5.2 СП 31-105"),
    (22, 4, False, None, "связи-распорки: проект фундамента по изысканиям — проектная организация"),
    (23, 2, True,  None, "анкерование обвязки производится"),
    (24, 2, True,  "Крепление стропил к мауэрлату", "стропила-мауэрлат: п. 8.2.2.6, 8.2.3.5 СП 31-105"),
    (25, 4, False, None, "расчёт обвязочного бруса на сдвиг — проектная организация"),
    (30, 3, False, None, "встречный: расчёт «слабого крепления»"),
    (31, 3, False, None, "встречный: сила ветра для срыва листа"),
    (32, 3, False, None, "встречный: какой документ требует крепления в каждую волну; + комплектация (ондулин в базе)"),
    (34, 2, True,  None, "стропила 38×95: отсос только для малых уклонов; уклоны 67°/32°, доп. стойка (сечения — СП 31-105 п. 8.2.1.x)"),
    (41, None, False, None, "сайдинг — коммерческая позиция «пусть так и будет»"),
    (45, 2, False, None, "мембрана под OSB, а не снаружи — фактическая технология"),
    (46, 2, True,  None, "вентзазор/контробрешётка — стандарт по СП 31-105, делается"),
    (50, 2, False, None, "вытяжки: 2 влажных помещения — 2 канала достаточно (нормы вентиляции)"),
    (51, 4, False, None, "кухонная вытяжка — прибор заказчика; отверстие делаем"),
    (52, 2, False, None, "рекуператор — изменение конструкции и удорожание; вентилятор на кухне есть"),
    (54, 2, False, "- Такой же бред", "стеклопакет: число стёкол влияет на термосопротивление; конденсат — отопление+вытяжка"),
    (57, 2, False, None, "OSB 9 мм: считали шаг лаг 300 мм"),
    (59, None, False, None, "брус 38×1900 — Алексей признал опечатку в документе"),
    (60, 2, False, None, "финишный пол — опция за доплату (комплектация)"),
    (61, 2, False, None, "дверь с терморазрывом — нужен холодный тамбур; замена за доплату"),
    (62, 2, False, None, "бойлер 50 л — базовая комплектация, 100 л за доплату"),
]
DISPUTED = {41: "коммерческая позиция — нет среди пяти типов", 59: "признание опечатки в документе — не «подтверждается нормативом»",
            46: "можно читать как 1 (норма подтверждает требование) — Алексей говорит «делаем по стандарту» → 2"}

def text_of(b, want):
    if b["kind"] == "p": parts = [t for L, t in b["layers"] if (L == "claim") == (want == "claim") and (want == "claim" or L.startswith("ans"))]
    else: parts = [t for c in b["cells"] for L, t in c if (L == "claim") == (want == "claim") and (want == "claim" or L.startswith("ans"))]
    return " ".join(" ".join(parts).split())

def kamenskoe():
    out = []
    for blk, v, sp31, cut, note in K:
        b = B[blk]; claim = text_of(b, "claim"); ans = text_of(b, "ans")
        if blk == 41:   # претензия про сайдинг — блоки 35–40 (ответ в 41)
            claim = " ".join(text_of(B[i], "claim") for i in range(35, 41))
        if cut and cut in claim:
            i = claim.index(cut); ans = (claim[i:] + " " + ans).strip(); claim = claim[:i].rstrip(" –-")
        if b["kind"] == "row":   # строка таблицы «что остаётся в силе»
            claim = " | ".join(" ".join(t for L, t in c if L == "claim").strip() for c in b["cells"])
        out.append({"id": f"K{blk:03d}", "source": "proverka-kamenskoe.docx", "claim": claim.strip(" –-"), "answer": ans,
                    "verdict": v, "needs_sp31_105": sp31, "note": note, "disputed": DISPUTED.get(blk)})
    return out

def pairs_file():
    t = open("/opt/captain-sam/materials/razbory/pary-voprosy-otvety.md", encoding="utf-8").read()
    secs = re.split(r"\n### ", t)
    out = []
    for s in secs[1:]:
        head = s.split("\n", 1)[0].strip()
        if not re.match(r"\d", head): continue
        q = re.search(r"\*\*(?:Вопрос клиента|Текст нейросети):\*\*\s*(.+?)(?=\n\*\*|\Z)", s, re.S)
        a = re.search(r"\*\*Ответ Алексея:\*\*\s*(.+?)(?=\n\*\*Что показательно|\n## |\Z)", s, re.S)
        n = head.split(".")[0]
        out.append({"id": f"P{n}", "source": "pary-voprosy-otvety.md", "title": head, "claim": " ".join((q.group(1) if q else "").split()),
                    "answer": " ".join((a.group(1) if a else "").split())})
    lab = {"P5": (3, "мощность — по теплотехническому расчёту для места строительства; нужны исходные данные (объект под вопросом)", "вопрос, не претензия; объект, возможно, не Каменское"),
           "P6": (None, "вопрос клиента, не претензия — информационный ответ по нормам", "вопрос, не претензия"),
           "P7": (None, "вопрос клиента, не претензия — информационный ответ по нормам", "вопрос, не претензия"),
           "P8": (None, "вопрос клиента, не претензия — расчёт тока", "вопрос, не претензия"),
           "P9–10": (3, "эталон по решению Вадима: встречный вопрос — при 15 кВт на одной фазе 63–80 А верно; какая мощность/фазность по ТУ", "Алексей опроверг (2), эталон Вадима — 3; посылка нейросети — 15 кВт на одной фазе")}
    for p in out:
        v, note, disp = lab.get(p["id"], (None, "", "не размечено"))
        p.update({"verdict": v, "needs_sp31_105": False, "note": note, "disputed": disp})
    return out

if __name__ == "__main__":
    E = kamenskoe() + pairs_file()
    json.dump(E, open("/opt/captain-sam/build/etalon.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from anonymize import anonymize
    for e in E:
        print(f"{e['id']:6} в={e['verdict']} sp31={int(e['needs_sp31_105'])} спор={'да' if e['disputed'] else '-'} | {anonymize(e['claim'])[0][:90]}")
    km = [e for e in E if e["id"].startswith("K")]
    print(f"\nКаменское: пар {len(km)}, с вердиктом {sum(e['verdict'] is not None for e in km)}, спорных {sum(bool(e['disputed']) for e in km)}, упирается в СП 31-105 {sum(e['needs_sp31_105'] for e in km)}")
