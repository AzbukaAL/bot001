"""П-13 (17.10.2026): роль без модели — ошибка на импорте, LLM_MODEL_<РОЛЬ> перебивает конфиг, имён моделей в коде нет.
  python3 src/test_llm_roles.py"""
import json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # 17.10: свой src — копия ветки не исполняет боевой код
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import llm_roles as LR

ok = 0; fail = []
def check(name, cond):
    global ok
    if cond: ok += 1
    else: fail.append(name)

def cfg(d):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); json.dump(d, f); f.close(); return f.name

full = {"mechanical": "m-1", "language": "l-1"}
check("обе роли из конфига", LR.load(cfg(full), env={}) == full)
check("переменная окружения перебивает", LR.load(cfg(full), env={"LLM_MODEL_LANGUAGE": "l-2"})["language"] == "l-2")
for bad in ({"mechanical": "m-1"}, {"mechanical": "m-1", "language": ""}, {}):
    try: LR.load(cfg(bad), env={}); check(f"нет роли {bad}", False)
    except RuntimeError as e: check(f"нет роли {bad}", "роль без модели" in str(e))
check("пустая роль в конфиге, задана окружением", LR.load(cfg({"mechanical": "m-1"}), env={"LLM_MODEL_LANGUAGE": "x"})["language"] == "x")
# на импорте: пустая роль — процесс не поднимается
env = dict(os.environ, LLM_MODEL_LANGUAGE=" ")
p = cfg({"mechanical": "m-1"})
r = subprocess.run([sys.executable, "-c", f"import json,sys; sys.path.insert(0,{ROOT + '/src'!r}); import llm_roles as L; L.load({p!r})"],
                   capture_output=True, text=True, env=env)
check("импорт падает при пустой роли", r.returncode != 0 and "роль без модели" in r.stderr)
src = "".join(open(f"{ROOT}/src/{f}", encoding="utf-8").read() for f in ("answer.py", "run08.py", "bot_max.py", "bot_tg.py"))
check("имён моделей в коде нет", not re.search(r"anthropic/|claude-|sonnet|gpt-|gemini", src))
check("у каждого chat() есть роль", all("role=" in l for l in src.splitlines() if re.search(r"\bchat\((SELECT|WRITE|JUDGE)_SYS", l)))
print(f"роли моделей: {ok}/{ok + len(fail)}", "" if not fail else f"ПРОВАЛ: {fail}")
sys.exit(1 if fail else 0)
