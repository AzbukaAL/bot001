"""Разбор proverka-kamenskoe.docx на блоки в порядке документа с цветовыми слоями (обезличено). Для разметки эталона."""
import sys, json, docx
from docx.table import Table
from docx.text.paragraph import Paragraph
sys.path.insert(0, "/opt/captain-sam/src")
from anonymize import anonymize

LAYER = {"000000": "claim", "auto": "claim", "ED7D31": "ans_orange", "4472C4": "ans_blue"}

def color(r):
    try: return str(r.font.color.rgb) if r.font.color is not None and r.font.color.rgb is not None else "auto"
    except Exception: return "auto"

def para_layers(p):
    out = []
    for r in p.runs:
        if not r.text: continue
        L = LAYER.get(color(r), "other:" + color(r))
        if out and out[-1][0] == L: out[-1][1] += r.text
        else: out.append([L, r.text])
    return out

def blocks(path):
    d = docx.Document(path); body = d.element.body; res = []
    for el in body.iterchildren():
        tag = el.tag.split("}")[1]
        if tag == "p":
            L = para_layers(Paragraph(el, d))
            if any(t.strip() for _, t in L): res.append({"kind": "p", "layers": L})
        elif tag == "tbl":
            t = Table(el, d)
            for ri, row in enumerate(t.rows):
                cells = [sum((para_layers(p) for p in c.paragraphs), []) for c in row.cells]
                res.append({"kind": "row", "row": ri, "cells": cells})
    return res

if __name__ == "__main__":
    B = blocks("/opt/captain-sam/materials/razbory/proverka-kamenskoe.docx")
    json.dump(B, open("/opt/captain-sam/build/kamenskoe_blocks.json", "w", encoding="utf-8"), ensure_ascii=False)
    for i, b in enumerate(B):
        if b["kind"] == "p":
            s = " | ".join(f"[{L}] {anonymize(' '.join(t.split()))[0][:110]}" for L, t in b["layers"])
        else:
            s = " || ".join(" ".join(f"[{L}] {anonymize(' '.join(t.split()))[0][:45]}" for L, t in c) for c in b["cells"])
        print(f"{i:03d} {b['kind']:3} {s[:330]}")
