"""OCR сканов из materials/normy/ (PDF без текстового слоя) → build/ocr/<файл>.txt. Уже распознанные пропускаются.
Распознанное в индексе помечается ocr=true; цитата из OCR клиенту — только после сверки с оригиналом (правило проекта)."""
import os, subprocess, tempfile, glob, sys, time
N, O = "/opt/captain-sam/materials/normy", "/opt/captain-sam/build/ocr"
os.makedirs(O, exist_ok=True)
for f in sorted(os.listdir(N)):
    if not f.endswith(".pdf"): continue
    out = os.path.join(O, f + ".txt")
    if os.path.exists(out): continue
    txt = subprocess.run(["pdftotext", os.path.join(N, f), "-"], capture_output=True, text=True).stdout
    if "_skan" in f: continue                                          # скан-дубль документа, чей текст уже есть
    weak = ("SP_17.13330.2017_bez_izm", "SP_256.1325800.2016_izm5", "SP_20.13330.2016_izm6")         # текстовый слой есть, но негодный — распознаём
    if len(txt.strip()) >= 200 and not any(w in f for w in weak): continue
    t0 = time.time()
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", os.path.join(N, f), os.path.join(d, "p")], check=True)
        pages = []
        for png in sorted(glob.glob(os.path.join(d, "p-*.png"))):
            r = subprocess.run(["tesseract", png, "-", "-l", "rus", "--psm", "6"], capture_output=True, text=True)
            pages.append(r.stdout)
    open(out, "w", encoding="utf-8").write("\n\f\n".join(pages))
    print(f"{f}: стр {len(pages)}, симв {sum(len(p) for p in pages)}, {time.time()-t0:.0f} с", flush=True)
print("готово")
