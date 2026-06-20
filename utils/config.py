import json

from colorama import Fore, Style


def load_config(translate, path="config.json"):
    """Load bot configuration from disk."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f'{Fore.RED}{translate("config_not_found")}{Style.RESET_ALL}')
        print(translate("config_create_instruction"))
        print(translate("config_example"))
        raise SystemExit(1)
    except json.JSONDecodeError:
        print(f'{Fore.RED}{translate("config_invalid_json")}{Style.RESET_ALL}')
        raise SystemExit(1)


def validate_config(cfg):
    """Warn at startup about missing or malformed config values."""
    owner_id = cfg.get("owner_id")
    if not owner_id:
        print(f"{Fore.YELLOW}[CONFIG] owner_id is not set - owner-only commands will not work.{Style.RESET_ALL}")
    else:
        try:
            int(str(owner_id))
        except ValueError:
            print(f'{Fore.RED}[CONFIG] owner_id "{owner_id}" is not a valid integer Discord ID.{Style.RESET_ALL}')


def save_config(cfg, path="config.json"):
    """Write the current config dict back to disk."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
