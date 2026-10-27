"""Прогон MVP-ответов по претензиям эталона: answer() на выбранных id, сверка вердикта с прогоном №8, стоимость.
  python3 src/mvp_run.py K054 K060 K061 K031 K021 P9–10     → build/mvp/run_<время>.json
"""
import json, sys, time
sys.path.insert(0, "/opt/captain-sam/src")
import answer as A

ROOT = "/opt/captain-sam"
ET = {e["id"]: e for e in json.load(open(f"{ROOT}/build/etalon.json", encoding="utf-8"))}
R8 = {r["id"]: r for r in json.load(open(f"{ROOT}/build/run08.json", encoding="utf-8"))}
ids = sys.argv[1:]
res, tin, tout = [], 0, 0
for i in ids:
    out, usage = A.answer(ET[i]["claim"])
    for u in usage: tin += u.get("prompt_tokens", 0); tout += u.get("completion_tokens", 0)
    v8 = R8.get(i, {}).get("system")
    out.update(id=i, run08_verdict=v8, same_as_run08=out["internal"]["verdict"] == v8)
    out.pop("mapping")   # обезличенный текст; исходные имена в файл прогона не пишем
    res.append(out)
    print(f"{i:6} вердикт={out['internal']['verdict']} (№8: {v8}) {'=' if out['same_as_run08'] else '≠'}  → {out['route']}"
          f"{'  [' + out['internal'].get('engineer_why', '') + ']' if out['route'] == 'engineer' else ''}", flush=True)
    time.sleep(0.5)
cost = (tin * A.R8.PRICE_IN + tout * A.R8.PRICE_OUT) / 1e6 * A.R8.USD
path = f"{ROOT}/build/mvp/run_{time.strftime('%m%d_%H%M')}.json"
import os; os.makedirs(f"{ROOT}/build/mvp", exist_ok=True)
json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.chmod(path, 0o640)
print(f"токенов: вход {tin}, выход {tout}; ≈ {cost:.1f} ₽ → {path}")
