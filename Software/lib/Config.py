import json
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = APP_DIR / "res" / "config.json"
COLOR_SCHEMES_FILE = APP_DIR / "res" / "colors.json"


def _read_json(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _load_config():
    return _read_json(CONFIG_FILE)

def _save_config(config):
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(config, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"Error saving config: {e}")

def getCFGKey(key: str, default=None):
    config = _load_config()
    return config.get(key, default)

def setCFGKey(key: str, value):
    config = _load_config()
    config[key] = value
    _save_config(config)


def getColorSchemes() -> dict[str, dict[str, str | list[str]]]:
    try:
        data = json.loads(COLOR_SCHEMES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error loading color schemes: {e}")
        return {}

    if not isinstance(data, dict):
        return {}

    parsed: dict[str, dict[str, str | list[str]]] = {}
    for name, scheme in data.items():
        if not isinstance(name, str) or not isinstance(scheme, dict):
            continue

        colors = scheme.get("colors")
        under = scheme.get("under")
        over = scheme.get("over")

        if not isinstance(colors, list) or not isinstance(under, str) or not isinstance(over, str):
            continue

        clean = [c for c in colors if isinstance(c, str) and c.strip()]
        if len(clean) >= 2:
            parsed[name] = {
                "colors": clean,
                "under": under,
                "over": over,
            }

    return parsed
