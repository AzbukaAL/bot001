"""Модели по ролям (стандарт ИИ-слоя, П-13, 17.10.2026). Имён моделей в коде нет: шаг объявляет роль,
модель роли — из config/llm_roles.json, переопределяется LLM_MODEL_<РОЛЬ>. Роль без модели — ошибка на импорте,
а не значение по умолчанию: молча подставленная модель хуже упавшего запуска (16.10 Polza сняла модель у соседнего контура)."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLES = ("mechanical", "language")

def load(path=f"{ROOT}/config/llm_roles.json", env=os.environ):
    cfg = json.load(open(path, encoding="utf-8"))
    out = {r: (env.get(f"LLM_MODEL_{r.upper()}") or cfg.get(r) or "").strip() for r in ROLES}
    miss = [r for r, m in out.items() if not m]
    if miss: raise RuntimeError(f"роль без модели: {miss} — {path} или LLM_MODEL_<РОЛЬ>")
    return out

MODELS = load()

def model(role): return MODELS[role]
