"""Утверждения регламента со ссылкой на пункт документа: предложение → (документ, пункт). Для сверки «пункт существует и
говорит то, что утверждается». Вход — обезличенный индекс «стандарт компании». Выход: build/reglament_claims.json."""
import json, re

idx = json.load(open("/opt/captain-sam/build/reglament_index.json", encoding="utf-8"))
DOC = re.compile(r"\b(ГОСТ\s?Р?\s?[\d.\-–]+(?:-\d{2,4})?|СП\s?\d[\d.]*(?:-\d{2,4})?)", re.I)
PT = re.compile(r"(?:\bп\.|\bпп\.|\bпункт[аеу]?|\bтабл\.|\bтаблиц[аеуы])\s*((?:[\dА-Я]+(?:\.\d+)*)(?:\s*(?:,|и)\s*[\d]+(?:\.\d+)*)*)", re.I)

def norm_doc(d):
    d = re.sub(r"\s+", " ", d).strip().rstrip(".,")
    return re.sub(r"^(ГОСТ Р|ГОСТ|СП)\s?", lambda x: x.group(1) + " ", d)

claims = []
for fid, v in idx.items():
    last = None   # документ из предыдущих предложений фрагмента: «…по СП 31-105. В п. 7.5.4 сказано…»
    for sent in re.split(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z«])", v["text"]):
        docs = [(m.start(), norm_doc(m.group(1))) for m in DOC.finditer(sent)]
        if docs: last = docs[-1][1]
        elif last and PT.search(sent): docs = [(-1000, last)]
        if not docs: continue
        for pm in PT.finditer(sent):
            kind = "табл." if "табл" in pm.group(0).lower() else "п."
            nums = re.split(r"\s*(?:,|и)\s*", pm.group(1))
            doc = min(docs, key=lambda d: abs(d[0] - pm.start()))[1]   # ближайшее обозначение в том же предложении
            for n in nums:
                n = n.strip().rstrip(".")
                if n and (n[0].isdigit() or re.fullmatch(r"[А-Я](\.\d+)*", n)): claims.append({"frag": fid, "doc": doc, "kind": kind, "point": n, "sentence": sent.strip()[:600]})
# дубли одного утверждения на один пункт — один раз
seen, out = set(), []
for c in claims:
    k = (c["doc"], c["kind"], c["point"], c["sentence"][:120])
    if k not in seen: seen.add(k); out.append(c)
json.dump(out, open("/opt/captain-sam/build/reglament_claims.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
print("утверждений со ссылкой на пункт:", len(out))
for d, n in Counter(c["doc"] for c in out).most_common(): print(f"  {d:28} {n}  " + ", ".join(sorted({c['kind'] + c['point'] for c in out if c['doc'] == d}))[:120])
