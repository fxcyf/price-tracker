"""Parse a browser-copied curl command to extract cookies and URL."""

import re
import shlex
from urllib.parse import urlparse


def parse_curl(curl_string: str) -> dict:
    """
    Parse a curl command string (copied from browser DevTools) and return
    a dict with 'url', 'cookies', and 'domain'.

    Example input:
        curl 'https://www.freepeople.com/shop/...' \\
          -H 'Accept: ...' \\
          -b '_px3=abc; urbn_country=US'

    Returns:
        {
            "url": "https://www.freepeople.com/shop/...",
            "domain": "freepeople.com",
            "cookies": {"_px3": "abc", "urbn_country": "US"},
        }
    """
    curl_string = curl_string.strip()

    # Remove line continuation backslashes so shlex can parse properly
    curl_string = re.sub(r"\\\n\s*", " ", curl_string)

    try:
        tokens = shlex.split(curl_string)
    except ValueError as e:
        raise ValueError(f"Failed to parse curl command: {e}")

    if not tokens or tokens[0].lower() != "curl":
        raise ValueError("Input does not appear to be a curl command")

    url = None
    cookies: dict[str, str] = {}

    i = 1
    while i < len(tokens):
        token = tokens[i]

        # URL (positional argument, not a flag)
        if not token.startswith("-") and url is None:
            url = token

        # -b or --cookie
        elif token in ("-b", "--cookie") and i + 1 < len(tokens):
            cookie_str = tokens[i + 1]
            for part in cookie_str.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    cookies[k.strip()] = v.strip()
            i += 1

        # -H with Cookie header (alternative to -b)
        elif token in ("-H", "--header") and i + 1 < len(tokens):
            header = tokens[i + 1]
            if header.lower().startswith("cookie:"):
                cookie_str = header[7:].strip()
                for part in cookie_str.split(";"):
                    part = part.strip()
                    if "=" in part:
                        k, v = part.split("=", 1)
                        cookies[k.strip()] = v.strip()
            i += 1

        i += 1

    if not url:
        raise ValueError("No URL found in curl command")

    hostname = urlparse(url).hostname or ""
    domain = hostname.removeprefix("www.")

    return {
        "url": url,
        "domain": domain,
        "cookies": cookies,
    }
