import json
from pathlib import Path


translations = {}
_logger = None


def load_translations(language="en", logger=None):
    """Load translation file based on language setting."""
    global translations
    global _logger
    if logger:
        _logger = logger

    lang_file = Path("lang") / f"{language}.json"

    try:
        if lang_file.exists():
            with lang_file.open("r", encoding="utf-8") as f:
                translations = json.load(f)
            if logger:
                logger.info(f"Loaded language: {language}")
        else:
            if logger:
                logger.warning(f"Language file '{lang_file}' not found, falling back to English")
            with Path("lang/en.json").open("r", encoding="utf-8") as f:
                translations = json.load(f)
    except Exception as exc:
        if logger:
            logger.error(f"Error loading translations: {exc}")
        translations = {}


def t(key, **kwargs):
    """Get translated string and replace placeholders."""
    text = translations.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError as exc:
            if _logger:
                _logger.error(f"Missing translation placeholder: {exc} in key '{key}'")
    return text
