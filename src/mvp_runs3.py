"""Проверка генератора v2 (09.10.2026): список из 5 претензий одним сообщением — N прогонов через обработчик бота (bot_max.handle,
тот же код, что в Telegram/MAX). Таблица по прогонам + лучший/худший (больше «готово для покупателя», при равенстве — меньше ⚠).
  python3 src/mvp_runs3.py /root/.emu5.txt 3   → build/mvp/runs3_<время>.md
"""
import json, sys, time
sys.path.insert(0, "/opt/captain-sam/src")
import bot_max as BM

ROOT = "/opt/captain-sam"
text = open(sys.argv[1], encoding="utf-8").read(); N = int(sys.argv[2]) if len(sys.argv) > 2 else 3
IDS = ["K054", "K061", "K045", "K031", "P9–10"]
runs = []
for n in range(N):
    import answer as A; A.USAGE.clear()
    paths, summary, outs = BM.handle(text)
    import run08 as R8_; tin = sum(u.get("prompt_tokens", 0) for u in A.USAGE); tout = sum(u.get("completion_tokens", 0) for u in A.USAGE)
    cost = (tin * R8_.PRICE_IN + tout * R8_.PRICE_OUT) / 1e6 * R8_.USD
    rows = []
    for k, o in zip(IDS, outs):
        i = o["internal"]
        rows.append({"id": k, "route": o["route"], "conclusion": o.get("conclusion") or (i.get("draft") or {}).get("conclusion"),
                     "basis": [b["label"] for b in (o.get("basis") or [])], "calc": bool(o.get("calc")),
                     "why": i.get("why_human"), "problems": len(i.get("problems") or [])})
    ready = sum(r["route"] == "client" for r in rows)
    runs.append({"n": n + 1, "paths": paths, "summary": summary, "rows": rows, "ready": ready, "problems": sum(r["problems"] for r in rows), "cost": round(cost, 1)})
    print(f"прогон {n + 1}: {summary} ≈ {cost:.0f} ₽", flush=True)
best = max(runs, key=lambda r: (r["ready"], -r["problems"])); worst = min(runs, key=lambda r: (r["ready"], -r["problems"]))
L = [f"# Генератор v2 — {N} прогона списка из 5 ({time.strftime('%d.%m.%Y %H:%M')} UTC)", "",
     "| Претензия | " + " | ".join(f"Прогон {r['n']}" for r in runs) + " |", "|---|" + "---|" * N]
for j, k in enumerate(IDS):
    cells = []
    for r in runs:
        x = r["rows"][j]
        cells.append(("✅ покупателю" if x["route"] == "client" else "→ инженеру") + f": {x['conclusion'] or '—'}"
                     + (f"; основание: {', '.join(x['basis'])}" if x["basis"] else "") + ("; расчёт" if x["calc"] else "")
                     + (f"; причина: {x['why']}" if x["route"] == "engineer" else ""))
    L.append(f"| {k} | " + " | ".join(cells) + " |")
L += ["", *[f"- Прогон {r['n']}: {r['summary']} Файлы: {', '.join(p.split('/')[-1] for p in r['paths'])}" for r in runs], "",
      f"**Лучший:** прогон {best['n']} (покупателю {best['ready']}/5). **Худший:** прогон {worst['n']} (покупателю {worst['ready']}/5).",
      f"Стоимость: {' + '.join(str(r['cost']) for r in runs)} ≈ {sum(r['cost'] for r in runs):.0f} ₽ (оценка по прайсу Anthropic)."]
path = f"{ROOT}/build/mvp/runs3_{time.strftime('%m%d_%H%M')}.md"; open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")
json.dump(runs, open(path[:-3] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n".join(L))
