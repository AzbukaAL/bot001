"""Стенд демо-набора: запись и воспроизведение вызовов модели (17.10.2026, стандарт ИИ-слоя).

Подменяет urllib.request.urlopen только для адреса Polza; остальной код не знает о стенде.
  record — настоящие вызовы; тело запроса (md5) и ответ пишутся в <out>/calls.jsonl
  replay — ответы берутся из записи по порядку, сеть не трогается; md5 тела сравнивается с записанным

  python3 src/llm_replay.py record build/standard-ai/before
  python3 src/llm_replay.py replay build/standard-ai/after --from build/standard-ai/before
  python3 src/llm_replay.py replay-md5 <out> --from <запись>   — ответ по md5 тела, а не по порядку (18.10): правка, которая
      убирает или добавляет вызовы, не сдвигает остальные; тело, которого нет в записи, — ошибка

Набор: Каменское 5 без КП; стеклопакет + КП «Тест 1»; котёл + опросный лист (синтетика) + теплотехнический расчёт.
Входные тексты — build/standard-ai/inputs/ (обезличиваются кодом до вызова модели, как в боте).
"""
import hashlib, io, json, os, sys, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INP = f"{ROOT}/build/standard-ai/inputs"
SET = [("kamenskoe5", "emu5.txt", []),
       ("steklo_kp", "cs_steklo.txt", [f"{ROOT}/materials/objects/test1-kp.pdf"]),
       ("kotel_docs", "claim_kotel.txt", [f"{ROOT}/build/mvp/test/oprosnyi-list-SINTETIKA-15kvt-3fazy.pdf",
                                          f"{ROOT}/materials/objects/teplotekh-raschet-kotel.pdf"])]
LLM_URL = "polza.ai/api/v1/chat/completions"

def etalon_set():
    """18.10: эталон v2 — Каменское с вердиктом инженера, P9–10, котёл R01 (с документами, как в демо); каждый пункт отдельно."""
    ET = json.load(open(f"{ROOT}/build/etalon_v2.json", encoding="utf-8"))
    out = []
    for e in ET:
        if (e["id"].startswith("K") and e.get("verdict") is not None) or e["id"] == "P9–10":
            out.append((e["id"], e["claim"], []))
        elif e["id"] == "R01":
            out.append((e["id"], e["claim"], SET[2][2]))
    return out

class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()

def main():
    mode, out = sys.argv[1], sys.argv[2]
    src = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else None
    os.makedirs(out, exist_ok=True); os.chmod(out, 0o750)
    rec = [json.loads(l) for l in open(f"{src}/calls.jsonl", encoding="utf-8")] if src else []
    by_md5 = {}
    for r0 in rec: by_md5.setdefault(r0["md5"], []).append(r0)
    log = []; real = urllib.request.urlopen
    CAP = float(sys.argv[sys.argv.index("--cap") + 1]) if "--cap" in sys.argv else 95.0; LIVE = [0.0]

    def fake(req, *a, **kw):
        url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
        if LLM_URL not in url: return real(req, *a, **kw)
        body = req.data; md5 = hashlib.md5(body).hexdigest(); n = len(log)
        e = {"n": n, "case": CASE[0], "md5": md5, "body": json.loads(body)}
        if mode == "record":
            try:
                with real(req, *a, **kw) as r: raw = r.read()
                e["resp"] = raw.decode()
            except Exception as ex:
                e["err"] = type(ex).__name__; log.append(e); raise
            log.append(e); return Resp(raw)
        if mode == "replay-md5-live" and not by_md5.get(md5):   # 18.10: нового тела нет в записи — настоящий вызов, с потолком ₽
            if LIVE[0] >= CAP: raise RuntimeError(f"стенд: потолок {CAP} ₽ исчерпан — прогон остановлен")
            with real(req, *a, **kw) as r: raw = r.read()
            LIVE[0] += float(json.loads(raw).get("usage", {}).get("cost_rub") or 0); e["live"] = True; e["resp"] = raw.decode(); log.append(e)
            return Resp(raw)
        if mode in ("replay-md5", "replay-md5-live"):
            if not by_md5.get(md5): raise RuntimeError(f"стенд: тела №{n} ({e['case']}) нет в записи — правка изменила запрос")
            r0 = by_md5[md5].pop(0); e["same"] = True; e["md5_before"] = md5; log.append(e)
        else:
            if n >= len(rec): raise RuntimeError(f"стенд: вызов №{n} сверх записи ({len(rec)})")
            r0 = rec[n]; e["same"] = r0["md5"] == md5; e["md5_before"] = r0["md5"]; log.append(e)
        if "err" in r0: raise urllib.error.URLError(f"записанный сбой {r0['err']}")
        return Resp(r0["resp"].encode())

    urllib.request.urlopen = fake
    import answer as A, bot_max as BM
    BM.OUT = out; A.CALLS_LOG = f"{out}/llm_calls.jsonl"   # журнал вызовов стенда — не в боевой
    CASE = [None]; summ = {}
    cases = etalon_set() if "--set" in sys.argv and sys.argv[sys.argv.index("--set") + 1] == "etalon" else \
            [(c, open(f"{INP}/{f}", encoding="utf-8").read(), d) for c, f, d in SET]
    for case, text, docs in cases:
        CASE[0] = case; t0 = time.time()
        BM.OUT = f"{out}/{case}"   # 18.10: свой каталог на случай — при подстановке случаи идут в одну секунду, имена файлов совпадали
        paths, summary, outs = BM.handle(text, docs or None)
        summ[case] = {"summary": summary, "paths": [p.split("/")[-1] for p in paths], "sec": round(time.time() - t0)}
        print(case, "|", summary.replace("\n", " / "), "|", summ[case]["sec"], "с", flush=True)
    with open(f"{out}/calls.jsonl", "w", encoding="utf-8") as fo:
        for e in log: fo.write(json.dumps(e, ensure_ascii=False) + "\n")
    json.dump(summ, open(f"{out}/summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for dp, dn, fn in os.walk(out):
        for p in fn: os.chmod(f"{dp}/{p}", 0o640)
    print("вызовов модели:", len(log))
    if mode == "replay-md5-live": print(f"новых вызовов: {sum(1 for e in log if e.get('live'))}, ₽ {LIVE[0]:.1f} (потолок {CAP})")
    if mode in ("replay-md5", "replay-md5-live"):
        print(f"по md5: из записи взято {sum(1 for e in log if not e.get('live'))} из {len(rec)} ответов, не понадобилось {sum(len(v) for v in by_md5.values())}")
    if mode == "replay":
        bad = [e["n"] for e in log if not e.get("same")]
        print(f"md5 тел: совпало {len(log) - len(bad)}/{len(log)}, записано было {len(rec)}", "" if not bad else f"РАСХОЖДЕНИЯ: {bad}")
        sys.exit(1 if bad or len(log) != len(rec) else 0)

if __name__ == "__main__":
    main()
