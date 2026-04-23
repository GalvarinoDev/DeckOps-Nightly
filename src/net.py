"""
net.py — DeckOps shared network utilities

Provides a reusable download-with-retry helper used by mod client
installers (cod4x, iw3sp, iw4x, cleanops). Centralises the browser
UA string and retry/backoff logic so changes propagate everywhere.
"""

import time
import urllib.request


BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
}


def download(url: str, dest: str, on_progress=None, label: str = "",
             timeout: int = 60):
    """
    Download a URL to a local file with chunked progress and retry.

    Reads in 1 MB chunks and reports download percentage via
    on_progress(percent: int, label: str).  Retries up to 3 times
    with exponential backoff on any network error.

    url         — remote URL to fetch
    dest        — local file path to write
    on_progress — optional callback(percent: int, label: str)
    label       — human-readable name shown in progress messages
    timeout     — socket timeout in seconds (default 60)
    """
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=BROWSER_UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                total = int(r.headers.get("Content-Length", 0))
                downloaded = 0
                with open(dest, "wb") as f:
                    while True:
                        chunk = r.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if on_progress and total:
                            on_progress(int(downloaded / total * 100), label)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
