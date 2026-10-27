"""Расход на модель за сутки — одной строкой Вадиму (17.10.2026, стандарт ИИ-слоя П-12).
Источник — журнал вызовов build/mvp/llm_calls.jsonl (пишет answer.log_call). Окно — 24 часа до отправки:
таймер captain-sam-cost раз в сутки в 14:00 UTC (20:00 Омск), так сутки не теряются и не считаются дважды.
  python3 src/daily_cost.py            → отправить
  python3 src/daily_cost.py --dry-run  → только напечатать
Журнала нет или он не читается — строка с 🔴, а не «0 ₽» (П-8: проверка без данных не говорит «всё в порядке»)."""
import datetime, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALLS_LOG = f"{ROOT}/build/mvp/llm_calls.jsonl"
BOT_OUT = f"{ROOT}/build/mvp/bot"
BOT_SRC = ("bot_max.py", "bot_tg.py")
NOTIFY_FAILED = f"{ROOT}/build/mvp/notify_failed.jsonl"   # 20.10: уведомления, не ушедшие после 3 попыток (bot_max.notify_retry)

def line(now, path=CALLS_LOG, bot_out=BOT_OUT, failed_path=NOTIFY_FAILED):
    since = now - datetime.timedelta(hours=24)
    head = f"💰 Расход на модель за сутки до {now.strftime('%d.%m %H:%M')} UTC"
    try: rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    except FileNotFoundError: return f"🔴 {head}: журнала вызовов нет — расход не известен"
    except Exception as e: return f"🔴 {head}: журнал вызовов не прочитан ({type(e).__name__}) — расход не известен"
    d = [r for r in rows if since <= datetime.datetime.strptime(r["ts"], "%Y-%m-%d %H:%M:%S") < now]
    bot = sum(r["rub"] for r in d if r.get("src") in BOT_SRC); other = sum(r["rub"] for r in d) - bot
    fails = sum(r.get("status") == "failed" for r in d)
    asks = sum(1 for f in glob.glob(f"{bot_out}/razbor_*.json")
               if since <= datetime.datetime.fromtimestamp(os.path.getmtime(f), datetime.UTC).replace(tzinfo=None) < now)
    try: lost = sum(1 for l in open(failed_path, encoding="utf-8") if l.strip()
                    and since <= datetime.datetime.strptime(json.loads(l)["ts"], "%Y-%m-%d %H:%M:%S") < now)
    except FileNotFoundError: lost = 0
    except Exception as e: lost = f"? ({type(e).__name__})"
    return (f"{head}: {bot + other:.0f} ₽ — бот {bot:.0f} ₽ ({asks} обращ.), прогоны {other:.0f} ₽; "
            f"вызовов {len(d)}" + (f", 🔴 сбоев {fails}" if fails else ", сбоев 0")
            + (f"; 🔴 уведомлений не ушло: {lost}" if lost else ""))

if __name__ == "__main__":
    t = line(datetime.datetime.now(datetime.UTC).replace(microsecond=0, tzinfo=None))
    print(t)
    if "--dry-run" not in sys.argv:
        import bot_max as BM
        BM.tg_send({"chat_id": BM.TG_ADMIN, "text": "Капитан Сэм\n" + t})   # осечка — ненулевой код, видно в журнале таймера
