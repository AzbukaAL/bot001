import json, sys
sys.path.insert(0, "/opt/captain-sam/src")
from anonymize import anonymize
B = "/opt/captain-sam/build"
REG = json.load(open(f"{B}/reglament_index.json", encoding="utf-8"))
R = {r["id"]: r for r in json.load(open(f"{B}/run06.json", encoding="utf-8"))}
E = {e["id"]: e for e in json.load(open(f"{B}/etalon.json", encoding="utf-8"))}
for i in sys.argv[1:]:
    r = R[i]
    print(f"== {i}: система {r['system']} (шаг {r.get('step')}, прямой {r.get('direct')}) / Алексей {r['etalon']}")
    print("   претензия:", anonymize(E[i]["claim"])[0][:220])
    print("   Алексей:", E[i]["note"])
    print("   обоснование:", (r["reason"] or "")[:320])
    for c in r["cite"] or []:
        if str(c).startswith("СК"): print(f"   [{c}]:", REG[c]["text"][:450])
