"""
net.py — DeckOps shared network utilities

Provides a reusable download-with-retry helper used by mod client
installers (cod4x, iw3sp, iw4x, cleanops). Centralises the browser
UA string and retry/backoff logic so changes propagate everywhere.
"""

import os
import time
import urllib.request

from log import get_logger

_log = get_logger(__name__)



BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
}


class DownloadError(RuntimeError):
    """
    Raised when a download fails after all retries.

    Carries the URL, destination path, and a human-readable label so the
    UI can offer a manual-download fallback dialog with a clickable link
    and a target folder for the user to place the file in.

    Attributes:
        url       -- the URL that failed to download
        dest      -- the local file path the download was targeting
        label     -- human-readable name (e.g. "Plutonium bootstrapper")
    """
    def __init__(self, url: str, dest: str, label: str, cause: Exception):
        self.url   = url
        self.dest  = dest
        self.label = label
        self.cause = cause
        super().__init__(
            f"{label} download failed after retries: {cause}"
        )


CHUNK      = 1024 * 1024
UPDATE_HZ  = 4          # cap on progress callbacks per second


def _fmt_size(n: int) -> str:
    if n >= 1 << 30: return f"{n / (1 << 30):.1f} GB"
    if n >= 100 << 20: return f"{n / (1 << 20):.0f} MB"
    if n >= 1 << 20: return f"{n / (1 << 20):.1f} MB"
    if n >= 1 << 10: return f"{n / (1 << 10):.0f} KB"
    return f"{n} B"


def _fmt_rate(bps: float) -> str:
    if bps >= 1 << 20: return f"{bps / (1 << 20):.1f} MB/s"
    if bps >= 1 << 10: return f"{bps / (1 << 10):.0f} KB/s"
    return f"{bps:.0f} B/s"


def _detail(label: str, done: int, total: int, rate: float) -> str:
    size = f"{_fmt_size(done)} / {_fmt_size(total)}" if total else _fmt_size(done)
    out = f"{label or 'Downloading'}  {size}"
    return f"{out}  ·  {_fmt_rate(rate)}" if rate else out


def download(url: str, dest: str, on_progress=None, label: str = "",
             timeout: int = 60, headers: dict = None):
    """
    Download a URL to a local file with resume, progress and retry.

    Writes to <dest>.part and renames on success, so a failed attempt
    leaves a partial file that the next attempt resumes from with a
    Range request. The part file is kept on failure deliberately, which
    is what makes a retry cheap on the multi-gigabyte downloads.

    Progress is reported as on_progress(percent, message) where message
    is the label with transferred size and rate appended, e.g.
    "AlterWare launcher  412 MB / 1.2 GB  ·  8.4 MB/s". Callbacks are
    capped at UPDATE_HZ per second.

    url         — remote URL to fetch
    dest        — local file path to write
    on_progress — optional callback(percent: int, status: str)
    label       — human-readable name shown in progress messages
    timeout     — socket timeout in seconds (default 60)
    headers     — request headers, default BROWSER_UA
    """
    part = dest + ".part"
    for attempt in range(3):
        resume = 0
        if os.path.exists(part):
            try:
                resume = os.path.getsize(part)
            except OSError:
                resume = 0
        try:
            hdrs = dict(headers or BROWSER_UA)
            if resume:
                hdrs["Range"] = f"bytes={resume}-"
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                # 206 means the range was honored. Anything else (including
                # a plain 200) means the server sent the whole file, so the
                # part file has to be discarded rather than appended to.
                status = getattr(r, "status", None) or getattr(r, "code", None)
                if resume and status != 206:
                    resume = 0
                length = int(r.headers.get("Content-Length", 0) or 0)
                total  = resume + length if length else 0
                done   = resume
                t0     = time.monotonic()
                last   = 0.0
                with open(part, "ab" if resume else "wb") as f:
                    while True:
                        chunk = r.read(CHUNK)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        now = time.monotonic()
                        if on_progress and now - last >= 1.0 / UPDATE_HZ:
                            last = now
                            rate = (done - resume) / max(now - t0, 0.001)
                            on_progress(int(done / total * 100) if total else 0,
                                        _detail(label, done, total, rate))
            # A stream that ends early used to look like success and get
            # renamed into place. Force a retry, which now resumes.
            if total and done < total:
                raise IOError(f"incomplete download: {done} of {total} bytes")
            os.replace(part, dest)
            if on_progress:
                on_progress(100, _detail(label, done, total or done, 0))
            return
        except Exception:
            if attempt == 2:
                raise
            _log.debug("download retry %d for %s", attempt + 1, url)
            time.sleep(2 ** attempt)
