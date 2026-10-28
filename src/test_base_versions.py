"""Тест версий базовых комплектаций (28.10.2026), без сети и без модели: реестр по синтетическим снимкам (две папки, повтор
блока по md5 — одна версия), выбор редакции по дате объекта (не позже; последняя из таких; без даты — не участвует),
модель из данных проекта, подключение к obj (позиции с источником «ред. … снимок …»), вопрос сотруднику вместо текущей базы,
ТО из договора — база сайта не подключается; строка вопроса в сводке бота. Плюс дымовая проверка реального снимка 28.10.
  python3 src/test_base_versions.py
"""
import glob, json, os, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import base_versions as BV, project_docs as PD, bot_max as BM

ok, fail = 0, []
def check(name, cond):
    global ok
    if cond: ok += 1
    else: fail.append(name)

TMP = tempfile.mkdtemp(prefix="bv-")
def snap(day, model, title, head, rows, md5tag):
    d = f"{TMP}/materials/reglament/bazovye-komplektacii-{day}/txt"; os.makedirs(d, exist_ok=True)
    body = f"{head}\nЭлемент Дома\nОписание Элемента Дома\n" + "\n".join(f"{a}\n{b}" for a, b in rows)
    open(f"{d}/{model}.txt", "w", encoding="utf-8").write(
        f"Источник: https://azbuka-doma.ru/proekty/x/y/{model}/\nЗагружено: {day} 05:00 UTC\nЗаголовок страницы: {title}\nmd5 блока: {md5tag}\n\n{body}\n")

ROWS1 = [("Фундамент", "Столбчатый из бетонных блоков"), ("Пол", "Лаги: брус – 38х140 мм. Шаг 600 мм. Чистовой пол - OSB 22 мм.")]
ROWS2 = [("Фундамент", "Столбчатый из бетонных блоков"), ("Пол", "Лаги: брус – 38х140 мм. Шаг 300 мм. Чистовой пол - OSB 22 мм.")]
snap("20260101", "test-6-kh-10", "Тест-хаус 6 х 10: каркасный дом под ключ — цена", "Базовая комплектация Тест-хаус\nДата: 14.11.24", ROWS1, "a")
snap("20260101", "zenit-6-kh-10", "Зенит 6 х 10: каркасный дом под ключ — цена", "Комплектация дома серии Зенит", ROWS1, "b")
snap("20260301", "test-6-kh-10", "Тест-хаус 6 х 10: каркасный дом под ключ — цена", "Базовая комплектация Тест-хаус\nДата: 22.05.26", ROWS2, "c")
snap("20260301", "zenit-6-kh-10", "Зенит 6 х 10: каркасный дом под ключ — цена", "Комплектация дома серии Зенит", ROWS1, "b")
snap("20260301", "sun-6-kh-9", "Каркасный дом Солнечный ++ 6 х 9 под ключ в Волгограде — цена", "Комплектация\nУтверждена приказом 2 от 30.09.2024", ROWS1, "d")

# реестр на синтетических снимках
BV.ROOT, BV.SNAP_GLOB, BV.REG = TMP, f"{TMP}/materials/reglament/bazovye-komplektacii-*", f"{TMP}/build/base_versions.json"
reg = BV.build_registry()
check("ключи моделей", set(reg["models"]) == {"тест-хаус 6 х 10", "зенит 6 х 10", "солнечный ++ 6 х 9"})
tv = reg["models"]["тест-хаус 6 х 10"]["versions"]
check("две редакции Тест-хаус по дате", [v["edition"] for v in tv] == ["2024-11-14", "2026-05-22"])
check("снимок первого появления", [v["snapshot"] for v in tv] == ["2026-01-01", "2026-03-01"])
check("повтор блока — одна версия", len(reg["models"]["зенит 6 х 10"]["versions"]) == 1 and reg["models"]["зенит 6 х 10"]["versions"][0]["edition"] is None)
check("«от ДД.ММ.ГГГГ» — редакция", reg["models"]["солнечный ++ 6 х 9"]["versions"][0]["edition"] == "2024-09-30")
check("имя модели из длинного заголовка", reg["models"]["солнечный ++ 6 х 9"]["name"] == "Солнечный ++ 6 х 9")
check("реестр читается из файла", BV.registry()["models"].keys() == reg["models"].keys())

# выбор редакции по дате объекта
check("дата между редакциями → ранняя", BV.edition_for("Тест-хаус 6х10", "2025-01-10", reg)["edition"] == "2024-11-14")
check("дата после последней → последняя", BV.edition_for("тест-хаус 6 х 10", "2026-06-01", reg)["edition"] == "2026-05-22")
check("дата = редакции → она", BV.edition_for("Тест-хаус 6 х 10", "2026-05-22", reg)["edition"] == "2026-05-22")
check("дата раньше всех → None", BV.edition_for("Тест-хаус 6 х 10", "2024-01-01", reg) is None)
check("редакция без даты не выбирается", BV.edition_for("Зенит 6 х 10", "2026-06-01", reg) is None)
check("неизвестная модель → None", BV.edition_for("Космос 6 х 10", "2026-06-01", reg) is None)
check("нет даты объекта → None", BV.edition_for("Тест-хаус 6 х 10", None, reg) is None)
check("нормализация размера", BV.norm("Барн-хаус 6×10") == BV.norm("барнхаус 6 х 10") == "барн-хаус 6 х 10" and BV.norm("Барн-хаус 6 х 7,4") == "барн-хаус 6 х 7.4")
check("iso дат", BV.iso("14.11.24") == "2024-11-14" and BV.iso("от 30.09.2024") == "2024-09-30" and BV.iso("—") is None and BV.ru("2024-11-14") == "14.11.2024")

# данные проекта → база
def obj(items, docs):
    return {"label": "Данные Вашего проекта (КП от 10.01.2025)", "date": "10.01.2025", "sources": "КП от 10.01.2025",
            "items": [dict(i, id=f"ОБ-1-{n:02d}", источник_метка="КП от 10.01.2025") for n, i in enumerate(items, 1)], "docs": docs}
KP = {"file": "kp.pdf", "kind": "КП", "date": "10.01.2025", "items": 2}
IT = [{"позиция": "Комплектация", "описание": "Базовая комплектация дома серии «Тест-хаус 2эт.», размер 6х10"}, {"позиция": "Фундамент", "описание": "свайный"}]
check("модель из данных проекта", BV.model_from(obj(IT, [KP]), reg) == "тест-хаус 6 х 10")
check("модель не найдена", BV.model_from(obj([{"позиция": "Фундамент", "описание": "свайный"}], [KP]), reg) is None)
check("дата объекта — КП", BV.obj_date(obj(IT, [KP])) == "2025-01-10")
check("дата объекта — самый ранний документ без КП", BV.obj_date(obj(IT, [{"kind": "опросный лист", "date": "05.03.2026", "items": 1},
                                                                        {"kind": "смета", "date": "01.02.2026", "items": 1}])) == "2026-02-01")
o = BV.attach(obj(IT, [KP]), reg)
check("база подключена", o["base"]["status"] == "ok" and o["base"]["edition"] == "2024-11-14" and o["base"]["items"] == 2)
bk = [i for i in o["items"] if i["id"].startswith("ОБ-БК-")]
check("позиции базы с источником", len(bk) == 2 and bk[1]["позиция"] == "Пол" and "Шаг 600" in bk[1]["описание"]
      and bk[1]["источник_метка"] == "базовая комплектация «Тест-хаус 6 х 10», ред. 14.11.2024, снимок сайта 01.01.2026")
check("источники и подпись дополнены", o["sources"].endswith("снимок сайта 01.01.2026") and o["label"].startswith("Данные Вашего проекта (КП от 10.01.2025; базовая"))
o2 = BV.attach(obj(IT, [dict(KP, date="01.06.2026")]), reg)
check("поздний договор → поздняя редакция (шаг 300)", o2["base"]["edition"] == "2026-05-22" and any("Шаг 300" in i["описание"] for i in o2["items"]))
o3 = BV.attach(obj(IT, [dict(KP, date="01.01.2024")]), reg)
check("договор раньше редакций → вопрос, позиций базы нет", o3["base"]["status"] == "не определена" and "не позже 01.01.2024" in o3["base"]["question"]
      and "14.11.2024, 22.05.2026" in o3["base"]["question"] and not any(i["id"].startswith("ОБ-БК-") for i in o3["items"]) and o3["sources"] == "КП от 10.01.2025")
o4 = BV.attach(obj([{"позиция": "Фундамент", "описание": "свайный"}], [KP]), reg)
check("модель не определена → вопрос", o4["base"]["status"] == "не определена" and "модель дома" in o4["base"]["question"])
o5 = BV.attach(obj(IT, [dict(KP, date=None)]), reg)
check("нет даты → вопрос с названием модели", o5["base"]["status"] == "не определена" and "дата КП/договора" in o5["base"]["question"] and "Тест-хаус 6 х 10" in o5["base"]["question"])
o6 = BV.attach(obj(IT, [KP, {"file": "to.pdf", "kind": "техническое описание", "date": "10.01.2025", "items": 5}]), reg)
check("ТО из договора выше сайта", o6["base"]["status"] == "ТО" and not any(i["id"].startswith("ОБ-БК-") for i in o6["items"]))
check("Зенит (редакция без даты) → вопрос", BV.attach(obj([{"позиция": "Дом", "описание": "серии Зенит 6х10"}], [KP]), reg)["base"]["status"] == "не определена")
check("obj None → None", BV.attach(None, reg) is None)

# сводка бота: вопрос сотруднику — отдельной строкой; при подключённой базе — её подпись в источниках
check("строка вопроса в сводке", BM.base_note(o3).startswith("\nВопрос сотруднику по базовой комплектации: для «Тест-хаус 6 х 10»"))
check("без вопроса — пусто", BM.base_note(o) == "" and BM.base_note(o6) == "" and BM.base_note(None) == "")

# build_docs подключает базу (attach вызывается; на тестовом опросном листе модели нет → вопрос, разбор не падает)
PD.BV = BV
obj_real, docs_real = PD.build_docs([f"{ROOT}/build/mvp/test/oprosnyi-list-SINTETIKA-15kvt-3fazy.pdf"])
check("build_docs: база обработана", obj_real is not None and obj_real.get("base", {}).get("status") == "не определена")

# дымовая проверка реального снимка 28.10 (если есть)
BV.ROOT, BV.SNAP_GLOB, BV.REG = ROOT, f"{ROOT}/materials/reglament/bazovye-komplektacii-*", f"{TMP}/build/base_versions_real.json"
if glob.glob(BV.SNAP_GLOB):
    r = BV.build_registry()
    b = r["models"].get("барн-хаус 6 х 10"); z = r["models"].get("зенит 6 х 10")
    check("реальный снимок: Барн-хаус 6 х 10, ред. 14.11.2024", bool(b) and b["versions"][-1]["edition"] == "2024-11-14")
    check("реальный снимок: Зенит — «приказ 2 от 30.09.2024»", bool(z) and z["versions"][-1]["edition"] == "2024-09-30")
    p = BV.parse_txt(f"{ROOT}/{b['versions'][-1]['file']}")
    check("реальный снимок: строки таблицы", dict(p["rows"]).get("Пол", "").startswith("Внутри обвязки") and "Шаг 600" in dict(p["rows"])["Пол"])
    check("реальный снимок: моделей ≥ 70", len(r["models"]) >= 70)
else:
    print("снимка нет — реальная проверка пропущена")

shutil.rmtree(TMP, ignore_errors=True)
print(f"test_base_versions: {ok} ок, {len(fail)} сбоев" + (": " + "; ".join(fail) if fail else ""))
sys.exit(1 if fail else 0)
