"""Показ последнего прогона MVP (обезличенные тексты): python3 src/mvp_show.py [файл]"""
import json, glob, sys
f = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("/opt/captain-sam/build/mvp/run_*.json"))[-1]
for r in json.load(open(f, encoding="utf-8")):
    print(f'\n## {r["id"]} → {r["route"]}  (вердикт {r["internal"]["verdict"]})')
    print("  претензия:", r["claim"][:200])
    for k, t in (("суть", r["essence"]), ("делаем", r["action"]), ("уточнить", r["clarify"])):
        if t: print(f"  {k}:", t)
    for b in r["basis"]: print("  основание:", b["label"], "«" + b["quote"][:200] + "»")
    if r["internal"].get("check"): print("  проверка:", r["internal"]["check"])
    if r["internal"].get("engineer_why"): print("  инженеру:", r["internal"]["engineer_why"])
