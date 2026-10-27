"""CI-4 (П-22, 17.10.2026): шаблоны текста — только по границам слов. Ловушки: подстрока внутри другого слова
не срабатывает, целое слово — срабатывает.  python3 src/test_word_bounds.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
import answer as A
from anonymize import anonymize

ok = 0; fail = []
def check(name, cond):
    global ok
    if cond: ok += 1
    else: fail.append(name)

TRAPS = [   # (шаблон, текст, должен ли сработать)
    ("FORMAL", "Конденсат в окне распространяется по стеклу", False),
    ("FORMAL", "Эта норма на каркасные дома не распространяется", True),
    ("FORMAL", "Влажность в стене нормируется СП 50", False),
    ("FORMAL", "Этот параметр не нормируется", True),
    ("OPTION", "неулучшенный вариант остекления", False),
    ("OPTION", "улучшенный стеклопакет", True),
    ("OPTION", "неопционально", False),
    ("OPTION", "доступно опционально", True),
    ("HEDGE", "ненужные данные из отчёта", False),
    ("HEDGE", "нужны данные о мощности", True),
    ("HEDGE", "всё зависит от проекта", True),
    ("HEDGE", "зависимость теплопотерь от площади", False),
    ("PROMISE", "непередаваемый инженерный опыт", False),
    ("PROMISE", "передадим инженеру", True),
    ("PROMISE", "мы вернёмся к Вам", True),
    ("PROMISE", "вернёмсяа", False),
    ("BUYER_OK", "Сколько жильцов будет в доме?", True),
    ("BUYER_OK", "Будет ли постоянное проживание?", True),
    ("BUYER_OK", "Вы планируете проживать круглогодично?", True),
    ("BUYER_OK", "сожильцы по договору", False),
    ("BUYER_OK", "непроживаемый объём чердака", False),
    ("BUYER_OK", "межсезонный режим", False),
]
for n, t, want in TRAPS:
    check(f"{n}: «{t}» → {want}", bool(getattr(A, n).search(t)) == want)

# «а» — союз, «А» — амперы (09.10)
check("ELECTRIC: союз «а» не электрика", not A.ELECTRIC.search("Стены утеплены, а кровля — нет"))
check("ELECTRIC: 25 А — электрика", bool(A.ELECTRIC.search("автомат на 25 А")))
check("ELECTRIC: «25 Ампер» без «А» отдельно", bool(A.ELECTRIC.search("ввод 25 А, автомат")))
# «Вас» — вежливое обращение, не имя (12.10); падежные формы имени — маскируются
check("«Вас» не маскируется", "<" not in anonymize("У Вас в КП указано")[0])
check("«Васе» маскируется", "<" in anonymize("Передайте Васе документы")[0])

print(f"границы слов: {ok}/{ok + len(fail)}", "" if not fail else f"ПРОВАЛ: {fail}")
sys.exit(1 if fail else 0)
