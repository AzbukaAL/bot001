import json
B = "/opt/captain-sam/build"
REG = json.load(open(f"{B}/reglament_index.json", encoding="utf-8"))
IDX = json.load(open(f"{B}/normy_index.json", encoding="utf-8"))
def src(d):
    if d in REG: return REG[d]["text"]
    if "|п." in d:
        doc, p = d.split("|п.", 1); return IDX.get(doc, {}).get("points", {}).get(p, {}).get("text", "")
    return ""
for r in json.load(open(f"{B}/run06b.json", encoding="utf-8")):
    if r["status"] != "ok" or r["id"] in ("K030", "K031"):
        d = str(r.get("direct") or "").strip("[]«»\"' ")
        ev = str(r.get("evidence") or "")
        s = src(d); norm = lambda x: " ".join(x.lower().split())
        # где расходится: самый длинный общий префикс
        n = 0; a, b = norm(ev.strip("«»\"' .…")), norm(s)
        while n < len(a) and a[:n + 1] in b: n += 1
        print(f"== {r['id']}: система {r['system']} / {r['status'][:70]} | прямой {d}")
        print(f"   evidence: {ev[:160]}")
        print(f"   совпало первых {n} из {len(a)} символов; дальше: «{a[n:n+40]}»")
