"""Тест приёмника данных проекта (15.10.2026), без вызовов модели: вид документа, отметки опросного листа,
параметры теплотехнического расчёта, источник с датой у каждой позиции, расчёт токов кодом.
Бланк заказчика (отметок нет) и синтетический заполненный лист — разные исходы, и это проверяется.
  python3 src/test_project_docs.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from anonymize import anonymize
import project_docs as PD, calc_electric as CE

M = f"{ROOT}/materials/objects"
B = f"{ROOT}/build/mvp/test"
BLANK, TEPLO = f"{M}/oprosnyi-list-kotel.pdf", f"{M}/teplotekh-raschet-kotel.pdf"
SINT = f"{B}/oprosnyi-list-SINTETIKA-15kvt-3fazy.pdf"

blank = PD.oprosnyi(BLANK)
sint = PD.oprosnyi(SINT)
tep = PD.teplo(TEPLO)
obj_blank, docs_blank = PD.build_docs([BLANK, TEPLO])
obj_sint, docs_sint = PD.build_docs([SINT, TEPLO])
tp = lambda o, rx: next((i["описание"] for i in o["items"] if rx in i["позиция"]), None)
Q = "электрокотел идет только на 220 вольт или на 380 можно? И вообще нужна ли такая мощность ,в чем смысл этой истории."
calc_sint, calc_blank = CE.from_project(obj_sint, Q), CE.from_project(obj_blank, Q)

# ── сводка сотруднику: источники, причина по неразобранному файлу, нужные данные по каждому пункту отдельной строкой ──
# Модель не вызывается: answer.answer подменён заглушкой, docx пишутся во временную папку.
import tempfile
import answer as AN, bot_max as BM
NEEDS = {"вопрос про кровлю": "тип кровельного покрытия, шаг обрешётки",
         "вопрос про котёл": "выделенная мощность и фазность по опросному листу"}
def fake_answer(claim, obj=None):
    return {"claim": claim, "mapping": {}, "route": "engineer", "conclusion": None, "short": None,
            "reasoning": AN.ENGINEER, "action": None, "clarify": None, "basis": [], "calc": [],
            "internal": {"verdict": None, "raw_verdict": 3, "status": "ok", "need_project": NEEDS.get(claim, "тип кровельного покрытия, шаг обрешётки"),
                         "why_human": "ответ зависит от данных проекта", "engineer_why": "нужны данные проекта",
                         "found": [], "draft": {}, "draft_basis": [], "problems": []}}, []
AN.answer, BM.OUT = fake_answer, tempfile.mkdtemp()
_, summary, _ = BM.handle("1. вопрос про кровлю\n2. вопрос про котёл", [BLANK, TEPLO])

checks = {
    "вид документа: опросный лист / теплотехнический расчёт / КП":
        PD.kind(BLANK) == "опросный лист" and PD.kind(TEPLO) == "теплотехнический расчёт"
        and PD.kind(f"{M}/test1-kp.pdf") == "КП",
    "дата документа — из метаданных PDF": PD.date_of(BLANK) == "09.10.2026" and PD.date_of(TEPLO) == "15.10.2026",
    "бланк заказчика: отметок нет → позиций нет и сказано почему":
        blank["items"] == [] and blank["marks"] == 0 and "незаполненный бланк" in blank["note"],
    "заполненный лист: отметка найдена, в описании — только отмеченная строка":
        len(sint["items"]) == 1 and sint["items"][0]["описание"] == "15кВт, 3фазы"
        and sint["items"][0]["позиция"] == "Выделенная мощность кВт и фазность" and sint["note"] is None,
    "теплотехнический расчёт: мощность котла одной позицией (требуемая и фактическая)":
        tp(tep, "Мощность котла") == "требуемая по расчёту 5, фактическая устанавливаемая 6",
    "теплотехнический расчёт: город, расчётная температура, утепление, остекление":
        tp(tep, "Город") == "Луганск" and tp(tep, "Расчётная температура") == "-23"
        and tp(tep, "Утеплитель стен") == "150" and tp(tep, "Площадь остекления") == "10,40",
    "у каждой позиции свой источник с датой":
        {i["источник_метка"] for i in obj_sint["items"]} ==
        {"опросный лист от 09.10.2026", "теплотехнический расчёт от 15.10.2026"},
    "сводный ярлык источников — оба документа с датами":
        obj_sint["sources"] == "опросный лист от 09.10.2026; теплотехнический расчёт от 15.10.2026",
    "бланк в перечне разобранного помечен причиной, расчёт — позициями":
        [(d["kind"], d["items"]) for d in docs_blank] == [("опросный лист", 0), ("теплотехнический расчёт", 15)]
        and "незаполненный бланк" in [d for d in docs_blank if d["kind"] == "опросный лист"][0]["note"],
    "непонятный файл не роняет разбор, а помечается":
        PD.build_docs([f"{ROOT}/config.json"])[1][0]["note"].startswith(("не разобрано", "вид документа не распознан")),
    "расчёт по данным проекта = числа инженера (27,3 А / 9,1 А / 2,0 кВт на фазу, лимит 5,0)":
        any("лимит на одну фазу 5,0 кВт" in l for l in calc_sint) and any("≈ 27,3 А" in l for l in calc_sint)
        and any("≈ 9,1 А" in l for l in calc_sint) and any("2,0 кВт и ток ≈ 9,1 А" in l for l in calc_sint)
        and any("больше лимита 5,0 кВт на фазу на 1,0 кВт" in l for l in calc_sint),
    "без заполненного листа: ток котла в обоих вариантах, ни слова про лимит, и сказано, чего не хватает":
        len(calc_blank) == 4 and any("27,3 А" in l for l in calc_blank) and any("9,1 А" in l for l in calc_blank)
        and not any("лимит" in l for l in calc_blank) and calc_blank[-1] == CE.NO_ALLOC,
    # Страховку answer.py (строка NO_ALLOC → пункт инженеру с перечнем нужных данных) этот тест проверить не может:
    # answer() ходит в модель. Она проверена живым прогоном 16.10 на бланке заказчика — журнал CLAUDE.md.
    "сводка: нужные данные — по строке на каждый пункт":
        "\nОтвет зависит от данных проекта:" in summary
        and "\nп. 1 — нужны тип кровельного покрытия, шаг обрешётки" in summary
        and "\nп. 2 — нужны выделенная мощность и фазность по опросному листу" in summary,
    "сводка: источники с датами и причина по неразобранному файлу":
        "Данные проекта: теплотехнический расчёт от 15.10.2026." in summary and "незаполненный бланк" in summary
        and "Пришлите данные проекта" not in summary,   # что-то из проекта разобрано — приглашения нет
    "сводка без данных проекта: приглашение прислать их есть":
        "Пришлите данные проекта — переделаю ответ." in BM.handle("1. вопрос про кровлю", None)[1],
    "ПДн в позициях проекта: меток 0":
        len(anonymize(str(obj_sint["items"]))[1]) == 0 and len(anonymize(str(tep["items"]))[1]) == 0,
}
for k, v in checks.items(): print(("✅ " if v else "❌ ") + k)
sys.exit(0 if all(checks.values()) else 1)
