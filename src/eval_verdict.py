"""Вердикт №8 по эталону v2 — тем же путём, что бот (answer.analyze: индекс бота, обезличивание, повторы), 17.10.2026.
Пункты: Каменское с вердиктом инженера + P9–10. Пишет build/index-fix/eval_<метка>.json: вердикт, статус, попытки
вердикта, исход первой попытки, ₽ по трассе.   python3 src/eval_verdict.py <метка>"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import answer as A

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tag = sys.argv[1]; out = f"{ROOT}/build/index-fix"; os.makedirs(out, exist_ok=True)
A.CALLS_LOG = f"{out}/calls_{tag}.jsonl"
ET = json.load(open(f"{ROOT}/build/etalon_v2.json", encoding="utf-8"))
todo = [e for e in ET if (e["id"].startswith("K") and e.get("verdict") is not None) or e["id"] in ("P9–10", "R01", "R02")]   # 21.10: + реальные кейсы
res = []
for e in todo:
    A.TRACE.clear(); t0 = time.time()
    a = A.analyze(e["claim"])
    vc = [x for x in A.TRACE if x["step"] == "verdict"]
    res.append({"id": e["id"], "etalon": e["verdict"], "verdict": a["verdict"], "raw": a["raw_verdict"], "status": a["status"],
                "direct": a["direct"], "verdict_calls": len(vc), "rub": round(sum(x["rub"] for x in vc), 2), "sec": round(time.time() - t0)})
    r = res[-1]; print(f"{r['id']:6} эталон={r['etalon']} система={r['verdict']} ({r['raw']}) вызовов={r['verdict_calls']} {r['status'][:50]}", flush=True)
json.dump(res, open(f"{out}/eval_{tag}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"совпало {sum(r['verdict'] == r['etalon'] for r in res)}/{len(res)}, ₽ {sum(r['rub'] for r in res):.1f}")
