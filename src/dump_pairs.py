import sys, json
sys.path.insert(0, "/opt/captain-sam/src")
from anonymize import anonymize
B = json.load(open("/opt/captain-sam/build/kamenskoe_blocks.json", encoding="utf-8"))
A = lambda t: anonymize(" ".join(t.split()))[0]
for i in list(range(17, 63)) + [85]:
    b = B[i]
    if b["kind"] == "p":
        cl = A(" ".join(t for L, t in b["layers"] if L == "claim")); an = [f"{L}: {A(t)}" for L, t in b["layers"] if L.startswith("ans")]
    else:
        cl = A(" | ".join(" ".join(t for L, t in c if L == "claim") for c in b["cells"])); an = [f"{L}: {A(t)}" for c in b["cells"] for L, t in c if L.startswith("ans")]
    if an: print(f"#{i:03d} ПРЕТЕНЗИЯ: {cl[:400]}\n      ОТВЕТ: " + " /// ".join(an)[:900] + "\n")
    else: print(f"#{i:03d} (без ответа) {cl[:160]}")
