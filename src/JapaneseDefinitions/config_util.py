import json
import os

from aqt import mw

ADDON_DIR = os.path.dirname(__file__)
USER_FILES_DIR = os.path.join(ADDON_DIR, "user_files")
OVERRIDES_PATH = os.path.join(USER_FILES_DIR, "overrides.json")

ADDON = mw.addonManager.addonFromModule(__name__)


DEFAULT_CONFIG = {
    # Fields
    "input_field": "Word",
    "definition_field": "Definition",
    "reading_field": "Reading",
    "pos_field": "POS",
    "overwrite_existing": False,

    # Definitions
    "number_of_definitions": "all",
    "definition_format": "plain",
    "capitalization": "first",          # none / all / first
    "replace_semicolons": True,

    # Reading (Input (Furigana))
    "fill_reading": False,
    "reading_format": "anki",           # kana / anki / ruby
    "furigana_granularity": "kanji",    # kanji / word

    # Part of speech
    "pos_placement": "none",            # none / field / inline
    "pos_label_style": "custom",        # full / code / custom
    "pos_separator": ", ",
    "pos_inline_template": "<i>({pos})</i> {definition}",
    "pos_inline_every_sense": False,
    "pos_labels": {},

    # Lookup
    "ignore_furigana": True,
    "deinflect": True,
    "preload_on_startup": True,
    "remember_choices": True,

    # Shortcuts
    "shortcut_reviewer_choose": "Ctrl+Alt+D",
    "shortcut_browser_choose": "Ctrl+Alt+D",
    "shortcut_browser_populate": "Ctrl+Alt+Shift+D",
    "shortcut_settings": "",
}

DEFAULT_OVERRIDES = {}


def _migrate(cfg):
    """Old keys -> new keys."""

    if "capitalization" not in cfg and (
        "capitalize_definition" in cfg or "capitalize_first_only" in cfg
    ):
        if cfg.get("capitalize_first_only"):
            cfg["capitalization"] = "first"
        elif cfg.get("capitalize_definition"):
            cfg["capitalization"] = "all"
        else:
            cfg["capitalization"] = "none"

    for old in ("capitalize_definition", "capitalize_first_only"):
        cfg.pop(old, None)

    if cfg.get("pos_placement") not in ("none", "field", "inline"):
        cfg["pos_placement"] = "none"

    return cfg


def get_config():

    cfg = mw.addonManager.getConfig(ADDON) or {}
    cfg = _migrate(dict(cfg))

    for key, value in DEFAULT_CONFIG.items():
        if key not in cfg:
            cfg[key] = value

    return cfg


def save_config(cfg):
    mw.addonManager.writeConfig(ADDON, cfg)


# ============================================================
# OVERRIDES (remembered choices)
# ============================================================

def load_overrides():

    if not os.path.exists(OVERRIDES_PATH):
        return dict(DEFAULT_OVERRIDES)

    try:
        with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"JapaneseDefinitions: could not read overrides: {e}")
        return {}


def save_overrides(overrides):

    try:
        os.makedirs(USER_FILES_DIR, exist_ok=True)
        with open(OVERRIDES_PATH, "w", encoding="utf-8") as f:
            json.dump(overrides, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"JapaneseDefinitions: could not save overrides: {e}")
