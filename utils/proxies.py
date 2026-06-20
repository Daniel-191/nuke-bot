import random
from pathlib import Path

from colorama import Fore, Style


def load_proxies():
    """Load SOCKS4 and SOCKS5 proxies from socks4.txt and socks5.txt."""
    proxies = []

    for scheme, filename in [("socks4", "socks4.txt"), ("socks5", "socks5.txt")]:
        path = Path(filename)
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "://" not in line:
                    line = f"{scheme}://{line}"
                proxies.append(line)

    return proxies


def configure_proxy(bot, config, logger):
    """Apply proxy configuration to the bot HTTP client when enabled."""
    if config.get("proxies", False):
        proxies = load_proxies()
        if proxies:
            try:
                from aiohttp_socks import ProxyConnector

                selected_proxy = random.choice(proxies)
                bot.http.connector = ProxyConnector.from_url(selected_proxy)
                print(f"{Fore.CYAN}[PROXY] {Fore.WHITE}Using proxy: {selected_proxy} ({len(proxies)} total loaded){Style.RESET_ALL}")
                logger.info(f"Proxy enabled: {selected_proxy} ({len(proxies)} proxies loaded)")
            except ImportError:
                print(f"{Fore.YELLOW}[PROXY] aiohttp_socks is not installed - proxies disabled. Run: pip install aiohttp_socks{Style.RESET_ALL}")
                logger.warning("aiohttp_socks not installed, proxies disabled")
        else:
            print(f"{Fore.YELLOW}[PROXY] Proxies enabled in config but no proxies found in socks4.txt / socks5.txt{Style.RESET_ALL}")
    else:
        print(f'{Fore.CYAN}[PROXY] {Fore.WHITE}Proxies disabled - set "proxies": true in config.json to enable{Style.RESET_ALL}')
