import json
import os

CONFIG_FILE = "config.json"
COLOR_SCHEMES_FILE = "colors.json"

def _load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
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
        with open(COLOR_SCHEMES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
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
