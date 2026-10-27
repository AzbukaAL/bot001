"""Эталон v2 (08.10.2026) — разметка инженера заказчика (materials/razbory/kamenskoe_engineer_v1.docx, 18 из 22 пар Каменского)
+ P5–P10 (позиция инженеров, подтверждено 06.10). Эталон v1 (позиция продаж) не трогается.
Вердикт пары: «Да» = вердикт системы в черновике (прогон №8); иначе — тип, названный первыми словами «Правки инженера»;
где тип не назван — выведен из текста (пометка), где не выводится однозначно — пара исключена из процента (спросить).
Ответы инженера — только для сверки, в промпт как примеры НЕ идут (это пары приёмки).
«Факт из эталона»: факт объекта (данные «Каменское») взят из ответа инженера на эту же претензию — в №9б совпадение по ним завышено.
  python3 src/etalon_v2.py  → build/etalon_v2.json
"""
import os
import json, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
from anonymize import anonymize
from docx import Document

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V1 = {e["id"]: e for e in json.load(open(f"{ROOT}/build/etalon.json", encoding="utf-8"))}
R8 = {r["id"]: r for r in json.load(open(f"{ROOT}/build/run08.json", encoding="utf-8"))}
HEAD = [(r"^подтверждается", 1), (r"^(претензия\s+)?(в\s+[\w\s«»]+\s+)?опровергается|^опровергается", 2),
        (r"^основани[ея] не найден", 5), (r"^обязательное устройство .* не следует", 2)]
DERIVED = {"K059": (1, "тип не назван: инженер подтверждает опечатку (как решение Вадима 01.10)"),
           "K062": (3, "тип не назван: нормы объём не устанавливают, инженер просит данные — встречный вопрос"),
           "K057": (2, "тип не назван: «к вашей конструкции пола не относится» (пол OSB 22, лаги 300) — опровергается фактом объекта")}
EXCLUDED = {"K021": "«частично корректна», тип не выводится однозначно — уточнить у Вадима/инженера"}
FACTS = re.compile(r"(?<![А-ЯЁа-яё])ЖБ(?![А-ЯЁа-яё])|(?i:железобетон|OSB 22|шаг(ом)? 300|уголк|саморез)")   # «жб» внутри «службы» — не факт
FORCE_FACT = {"K060"}   # указание Вадима 08.10: «K057, K060 и подобные»

out = []
for r in Document(f"{ROOT}/materials/razbory/kamenskoe_engineer_v1.docx").tables[0].rows[1:]:
    c = [x.text.strip() for x in r.cells]; k, ok, fix = c[0], c[7], " ".join(c[8].split())
    if not ok and not fix: continue
    e = {"id": k, "source": "kamenskoe_engineer_v1.docx", "claim": V1[k]["claim"], "answer": anonymize(fix)[0], "engineer_ok": ok}
    if k in EXCLUDED: e.update(verdict=None, verdict_source="исключено: " + EXCLUDED[k])
    elif ok.lower().startswith("да"): e.update(verdict=R8[k]["system"], verdict_source="«Да» — вердикт системы №8 верен")
    elif k in DERIVED: e.update(verdict=DERIVED[k][0], verdict_source="выведено из текста: " + DERIVED[k][1])
    else:
        v = next((t for rx, t in HEAD if re.search(rx, fix.lower())), None)
        e.update(verdict=v, verdict_source="явно, первыми словами правки" if v else "НЕ РАСПОЗНАНО — проверить")
    e["fact_from_etalon"] = bool(FACTS.search(fix)) or k in FORCE_FACT
    e["etalon_status"] = "v2 — разметка инженера заказчика (08.10)"
    out.append(e)
for k, e in V1.items():
    if k.startswith("P"): out.append({**e, "source": e["source"], "verdict_source": "P5–P10 — позиция инженеров, подтверждено 06.10",
                                      "fact_from_etalon": False, "etalon_status": "позиция инженеров, подтверждено 06.10"})
# 15.10.2026: реальные кейсы бота с ответом инженера заказчика — materials/razbory/<кейс>.md (пара «вопрос — ответ»).
# В примеры стиля генератора (style_examples: P5, P8) НЕ идут: это пары приёмки.
import glob, os
REAL = {"kotel-15102026.md": {"verdict": None, "fact_from_etalon": True,
        "verdict_source": "вопрос покупателя, не претензия — ответ по данным проекта и расчёт токов (как P8)",
        "fact_from_etalon_why": "«15 кВт, 3 фазы» и «5 кВт на фазу» есть только в ответе инженера: присланный опросный лист — пустой бланк",
        "etalon_status": "реальный кейс бота 12.10.2026, ответ инженера 15.10.2026"},
        # 21.10.2026: R02 — вопрос с подразумеваемым требованием («почему не предусмотрен слив»); инженер: норма допускает
        # замену слива продувкой (СП 60 п. 6.2.16, исключение для горизонтальных систем с полимерными трубами) — тип 2
        "sliv-otopleniya-21102026.md": {"verdict": 2, "fact_from_etalon": True,
        "verdict_source": "ответ инженера заказчика: требование опровергается нормативом (исключение СП 60 п. 6.2.16)",
        "fact_from_etalon_why": "горизонтальная система, полимерные трубы, алюминиевые радиаторы — только в ответе инженера",
        "etalon_status": "реальный кейс бота 21.10.2026, ответ инженера 21.10.2026 (источник — заказчик)"}}
for f in sorted(glob.glob(f"{ROOT}/materials/razbory/*.md")):
    name = os.path.basename(f)
    if name not in REAL: continue
    t = open(f, encoding="utf-8").read()
    for sec in re.split(r"\n### ", t)[1:]:
        head = sec.split("\n", 1)[0].strip()
        m = re.match(r"(R\d+)\.\s*(.+)", head)
        if not m: continue
        q = re.search(r"\*\*Вопрос покупателя:\*\*\s*(.+?)(?=\n\*\*|\Z)", sec, re.S)
        a = re.search(r"\*\*Ответ инженера:\*\*\s*(.+?)(?=\n\*\*|\n## |\Z)", sec, re.S)
        e = {"id": m.group(1), "source": name, "title": m.group(2),
             "claim": anonymize(" ".join((q.group(1) if q else "").split()))[0],
             "answer": anonymize(" ".join((a.group(1) if a else "").split()))[0],
             "engineer_ok": "ответ инженера заказчика"}
        e.update(REAL[name]); out.append(e)

json.dump(out, open(f"{ROOT}/build/etalon_v2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for e in out: print(f"{e['id']:6} v1={(V1.get(e['id']) or {}).get('verdict')} → v2={e['verdict']}  факт_из_эталона={'да' if e['fact_from_etalon'] else '—'}  [{e['verdict_source'][:70]}]")
