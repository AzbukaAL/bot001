"""Стабильность демо-набора: каждая претензия N раз через обработчик бота (bot_max.handle — тот же, что у Telegram/MAX).
В показ — только претензии, где все N ответов ушли клиенту по одному основанию и по существу.
  python3 src/mvp_stability.py 3      → build/mvp/stability_<время>.json и .md
"""
import json, sys, time, collections
sys.path.insert(0, "/opt/captain-sam/src")
import bot_max as BM

ROOT = "/opt/captain-sam"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3
ET = {e["id"]: e for e in json.load(open(f"{ROOT}/build/etalon.json", encoding="utf-8"))}
CLEAN = {"K061": "Входная дверь (КНР) без терморазрыва — зимой при −7 °C и ветре будет промерзать."}
LIVE = json.load(open(f"{ROOT}/build/mvp/bot/otvet_20261008_035546.json", encoding="utf-8"))[0]["claim"]   # K054 в формулировке Вадима
TEXT = {"K054": LIVE}
IDS = ["K054", "K061", "K045", "K031", "K021", "P9–10"]

rows = []
for k in IDS:
    text = TEXT.get(k) or CLEAN.get(k) or ET[k]["claim"]
    runs = []
    for n in range(N):
        _, _, outs = BM.handle(text); o = outs[0]; i = o["internal"]; j = i.get("judge") or {}
        runs.append({"route": o["route"], "verdict": i.get("verdict"),
                     "basis": (o["basis"][0]["ref"] if o["basis"] else ("встречный вопрос" if o.get("clarify") else "—")),
                     "on_point": bool(j.get("addresses")) and o["route"] == "client", "why": i.get("engineer_why")})
        time.sleep(0.5)
    stable = all(r["route"] == "client" and r["on_point"] for r in runs) and len({r["basis"] for r in runs}) == 1
    rows.append({"id": k, "runs": runs, "demo": stable})
    print(k, "→", "В ПОКАЗ" if stable else "исключить", [(r["route"], r["basis"], r["on_point"]) for r in runs], flush=True)

ts = time.strftime("%m%d_%H%M"); base = f"{ROOT}/build/mvp/stability_{ts}"
json.dump(rows, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
L = [f"# Стабильность демо-набора ({N} прогона через обработчик бота, {time.strftime('%d.%m.%Y %H:%M')} UTC)", "",
     "| Претензия | " + " | ".join(f"Прогон {n+1}: основание / по существу / инженеру" for n in range(N)) + " | Итог |",
     "|---|" + "---|" * N + "---|"]
for r in rows:
    cells = [f"{x['basis']} / {'да' if x['on_point'] else 'нет'} / {'да' if x['route'] == 'engineer' else 'нет'}" for x in r["runs"]]
    L.append(f"| {r['id']} | " + " | ".join(cells) + f" | {'**в показ**' if r['demo'] else 'исключить'} |")
L += ["", "Причины ухода инженеру:"] + [f"- {r['id']}, прогон {n+1}: {x['why']}" for r in rows for n, x in enumerate(r["runs"]) if x["why"]]
open(base + ".md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print("→", base + ".md")
