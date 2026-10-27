"""Регламент (стандарт компании): текст из materials/reglament/*.docx|*.odt → обезличенный → build/reglament/*.txt + отчёт.
Сырые тексты в вывод не печатаются (правило 7 CLAUDE.md проекта)."""
import os, re, sys, json, zipfile, collections
from xml.etree import ElementTree as ET
sys.path.insert(0, "/opt/captain-sam/src")
from anonymize import anonymize
import docx
R, O = "/opt/captain-sam/materials/reglament", "/opt/captain-sam/build/reglament"
os.makedirs(O, exist_ok=True)

def docx_lines(p):
    d = docx.Document(p); out = []
    for el in d.element.body.iterchildren():
        tag = el.tag.split("}")[1]
        if tag == "p":
            par = docx.text.paragraph.Paragraph(el, d); t = par.text.strip()
            if t: out.append((par.style.name if par.style is not None else "", t))
        elif tag == "tbl":
            tb = docx.table.Table(el, d)
            for row in tb.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells): out.append(("table", " | ".join(dict.fromkeys(cells))))
    return out

def odt_lines(p):
    ns = {"text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
    x = ET.fromstring(zipfile.ZipFile(p).read("content.xml"))
    out = []
    for el in x.iter():
        tag = el.tag.split("}")[1]
        if tag in ("h", "p"):
            t = "".join(el.itertext()).strip()
            if t: out.append(("heading" if tag == "h" else "p", t))
    return out

rep = {}
for f in sorted(os.listdir(R)):
    p = os.path.join(R, f)
    if f.endswith(".docx"): L = docx_lines(p)
    elif f.endswith(".odt"): L = odt_lines(p)
    else: continue
    text = "\n".join(t for _, t in L)
    anon, mp = anonymize(text)
    open(os.path.join(O, f + ".anon.txt"), "w", encoding="utf-8").write(anon)
    json.dump([(s, anonymize(t)[0]) for s, t in L], open(os.path.join(O, f + ".lines.json"), "w", encoding="utf-8"), ensure_ascii=False)
    kinds = collections.Counter(k.strip("<>").rsplit("_", 1)[0] for k in mp)
    rep[f] = {"строк": len(L), "символов": len(text), "ПДн-меток": dict(kinds)}
    print(f"== {f}: строк {len(L)}, символов {len(text)}, обезличиватель нашёл: {dict(kinds) or 'ничего'}")
    styles = collections.Counter(s for s, _ in L); print("   стили:", dict(styles.most_common(6)))
    # структура: заголовки и нумерованные блоки верхнего уровня (обезличенно, коротко)
    for s, t in L:
        a = anonymize(t)[0]
        if s.lower().startswith(("heading", "заголов", "title")) or s == "heading" or re.match(r"^\s*\d{1,2}[.)]\s", a) and len(a) < 140:
            print("   ", s[:10].ljust(10), a[:120])
json.dump(rep, open(os.path.join(O, "anon_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
