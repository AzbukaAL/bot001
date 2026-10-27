"""Раздел СК-ИНЖ «Система отопления: слив и теплоноситель» (21.10.2026, решение Вадима): словами инженера, пп. 1, 2, 3, 5, 6;
п. 4 — внесён 21.10 с уточнением С. Бердникова и примечанием опросного листа.  python3 src/test_heating_section.py"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import answer as A
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R02_FILE = next((p for p in (f"{ROOT}/materials/razbory/sliv-otopleniya-21102026.md", "/opt/captain-sam/materials/razbory/sliv-otopleniya-21102026.md", "/opt/captain-sam-wt-exc/materials/razbory/sliv-otopleniya-21102026.md") if __import__("os").path.exists(p)), "")

ok = 0; fail = []
def check(name, cond):
    global ok
    if cond: ok += 1
    else: fail.append(name)

refs = [k for k, v in A.R8.REG.items() if v.get("section_name") == "Система отопления: слив и теплоноситель"]
text = " ".join(A.R8.REG[k]["text"] for k in sorted(refs))
check("раздел в индексе", len(refs) >= 1)
check("подпись с источником", all("позиция инженера: Система отопления: слив и теплоноситель; источник: инженер заказчика, 21.10.2026" in A.label_engineer(k) for k in refs))
for n in ("1. Принцип работы и слив воды", "2. Алюминиевые радиаторы и окисление", "3. Недопустимость слива на зиму", "4. Альтернатива — антифриз",
          "5. Замена радиаторов", "6. Нормативное обоснование"):
    check(f"есть пункт: {n}", n in text)
check("п. 4 внесён", "4. Альтернатива — антифриз (с оговорками)" in text and "снятие с гарантии" in text)
check("уточнение С. Бердникова дословно", "«слетает в любом случае. может разъедать резиновые уплотнители. о снятии с гарантии есть примечание в опросном листе»" in text)
check("примечание опросного листа дословно", "«Антифриз приобретается заказчиком. При заполнении антифризом, гарантия на систему отопления не действует.»" in text)
check("ПДн в тексте нет", not re.search(r"<[А-ЯA-Z]+_\d+>", text))
r02 = open(R02_FILE, encoding="utf-8").read() if R02_FILE else ""
if r02:
    ans = " ".join(r02.split("**Ответ инженера:** ", 1)[1].split())
    check("дословно из ответа инженера (п. 1–6)", all(" ".join(p.split()) in ans for p in re.split(r"(?=\b[1-6]\. [А-Я])", text.split(" Уточнение инженера")[0]) if p.strip()))
check("раздел — кандидат для вопроса R02", any(k in A.R8.reg_candidates("почему не предусмотрен слив воды с системы отопления?") for k in refs))
check("позиция 15.10 — прежняя подпись", A.label_engineer("СК-ИНЖ §1.1") == "Стандарт компании (позиция инженера, 15.10.2026), раздел 1.1")
print(f"раздел «Система отопления»: {ok}/{ok + len(fail)}", "" if not fail else f"ПРОВАЛ: {fail}")
sys.exit(1 if fail else 0)
