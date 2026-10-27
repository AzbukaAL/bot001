# Состав системы: ядро и сторонние компоненты

Перечень для договора (п. 2.2 — ядро, передаваемое заказчику; п. 2.7 — сторонние компоненты и их лицензии).
Версии — по серверу на 27.10.2026.

## Ядро (собственная разработка, передаётся по договору)

| Компонент | Файлы |
|---|---|
| Обработчик претензии: пункты, обезличивание, поиск оснований, вердикт, проверка цитат, генерация ответа | `src/answer.py`, `src/run08.py`, `src/claim_doc.py`, `src/anonymize.py`, `src/pdn_check.py` |
| Индексы: нормы (с таблицами СП 131 построчно), стандарт компании, данные объекта | `src/normy_parse.py`, `src/climate_sp131.py`, `src/ocr_scans.py`, `src/pdf_columns.py`, `src/reglament_*.py`, `src/object_index.py`, `src/project_docs.py` |
| Расчёты кодом | `src/calc_electric.py`, `src/calc_teplo.py` |
| Оформление и доставка: DOCX, боты MAX и Telegram, сводка, настройка тона, отчёт о расходе | `src/answer_docx.py`, `src/bot_max.py`, `src/bot_tg.py`, `src/daily_cost.py`, `src/llm_roles.py` |
| Тесты, стенд записи/воспроизведения вызовов модели, прогоны и эталон | `src/test_*.py`, `src/llm_replay.py`, `src/run0*.py`, `src/mvp_*.py`, `src/etalon*.py`, `src/eval_verdict.py` |
| Настройки и развёртывание | `config.json`, `config/llm_roles.json`, `deploy/*.service`, `deploy/*.timer` |

## Сторонние компоненты (open source)

| Компонент | Версия | Лицензия | Для чего |
|---|---|---|---|
| Python | 3.12 | PSF License | язык и стандартная библиотека (http, json, re, zipfile, xml) |
| python-docx (+ lxml) | 1.2.0 (lxml 6.0) | MIT (lxml — BSD-3-Clause) | чтение и создание DOCX |
| pdfplumber | 0.11.9 | MIT | текст и таблицы из PDF с текстовым слоем |
| pdfminer.six | 20251230 | MIT | зависимость pdfplumber |
| pypdfium2 (PDFium) | 5.8.0 | BSD-3-Clause / Apache-2.0 | зависимость pdfplumber |
| Pillow | 12.1 | MIT-CMU (HPND) | зависимость pdfplumber |
| beautifulsoup4 (+ soupsieve) | 4.14.3 | MIT | разбор HTML/XML |
| poppler-utils (`pdftotext`, `pdftoppm`) | 24.02 | GPL-2.0-or-later | извлечение текста PDF, растр страниц для OCR; вызывается как внешняя программа |
| tesseract-ocr + tesseract-ocr-rus | 5.3.4 / 4.1.0 | Apache-2.0 | распознавание сканов норм |
| systemd | Ubuntu 24.04 | LGPL-2.1-or-later | запуск служб (только юнит-файлы в `deploy/`) |

GPL-компоненты (poppler) используются как отдельные программы через вызов процесса, в код ядра не встраиваются.

## Внешние сервисы (по условиям использования поставщика)

| Сервис | Для чего | Условия |
|---|---|---|
| polza.ai — шлюз API моделей (OpenAI-совместимый) | вызовы моделей по ролям; модель на 27.10.2026 — `anthropic/claude-sonnet-4.5` (`config/llm_roles.json`) | договор/оферта polza.ai; политика использования Anthropic |
| MAX Bot API (`platform-api2.max.ru`) | бот MAX | условия платформы MAX |
| Telegram Bot API (`api.telegram.org`) | бот Telegram, уведомления администратору | условия Telegram |

## Данные (в репозиторий не входят)

| Данные | Источник | Права |
|---|---|---|
| Тексты норм (СП, ГОСТ) | копии заказчика и Минстроя в `materials/normy/` | публичные нормативные документы; индекс строится на сервере |
| Стандарт компании, позиции инженера | `materials/reglament/` | заказчик |
| Документы объектов, разборы, обращения покупателей | `materials/objects/`, `materials/razbory/`, `build/` | заказчик; содержат ПДн, в git и в модель не передаются |
