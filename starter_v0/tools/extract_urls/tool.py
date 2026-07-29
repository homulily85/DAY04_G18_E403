from __future__ import annotations

import re

_URL_RE = re.compile(r"https?://[^\s<>()\"']+")


def extract_urls(text: str = "") -> dict:
    urls = _URL_RE.findall(text or "")
    seen: set[str] = set()
    unique_urls: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    return {
        "tool": "extract_urls",
        "urls": unique_urls,
        "count": len(unique_urls),
        "error": None,
    }
