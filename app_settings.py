# app_settings.py
import json, os
from pathlib import Path
from typing import Any, Dict
from paths import PROJECT_ROOT

CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_PATH = CONFIG_DIR / "settings.json"

DEFAULTS: Dict[str, Any] = {
    "export_dir": str((PROJECT_ROOT / "exports").resolve()),
}

def load_settings() -> Dict[str, Any]:
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            out = dict(DEFAULTS); out.update({k: v for k, v in data.items() if k in DEFAULTS})
            return out
        except Exception:
            pass
    return dict(DEFAULTS)

def save_settings(new_settings: Dict[str, Any]) -> None:
    s = dict(DEFAULTS); s.update(new_settings or {})
    p = Path(s["export_dir"]).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    s["export_dir"] = str(p)
    SETTINGS_PATH.write_text(json.dumps(s, indent=2), encoding="utf-8")

def get_export_dir() -> Path:
    p = Path(load_settings()["export_dir"]).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p
