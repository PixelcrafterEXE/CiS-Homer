import json
import os

CONFIG_FILE = "config.json"

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
