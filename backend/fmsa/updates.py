"""Check GitHub releases for a newer FMSaveAnalyst.

The only request is an anonymous GET to the GitHub API for the project's latest release; nothing
about the user or their data is sent. The app never downloads or installs anything by itself: it
shows the release notes and opens the release page in the browser.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

from fmsa import __version__

log = logging.getLogger(__name__)

REPOSITORY = "GiorgioGandolfi88/FMSaveAnalyst"
LATEST_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases"
USER_AGENT = f"FMSaveAnalyst/{__version__} (update check)"
CACHE_SECONDS = 6 * 3600
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+.]?(.*))?$")


def parse_version(text: str) -> tuple[int, int, int, bool] | None:
    """(major, minor, patch, is_final); pre-releases (e.g. 1.2.0-beta) sort before the final."""
    m = _VERSION.match(text.strip())
    if not m:
        return None
    return int(m[1]), int(m[2]), int(m[3]), not m[4]


def is_newer(candidate: str, current: str) -> bool:
    a, b = parse_version(candidate), parse_version(current)
    return bool(a and b and a > b)


@dataclass(slots=True)
class UpdateInfo:
    current: str
    latest: str | None = None
    update_available: bool = False
    url: str = RELEASES_PAGE
    notes: str = ""
    published_at: str | None = None
    download_url: str | None = None
    error: str | None = None
    checked_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fetch(timeout: float) -> dict[str, Any] | None:
    request = urllib.request.Request(
        LATEST_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:  # no release published yet
            return None
        raise


def check(current: str = __version__, timeout: float = 6.0) -> UpdateInfo:
    info = UpdateInfo(current=current, checked_at=time.time())
    try:
        release = _fetch(timeout)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        log.info("Update check failed: %s", exc)
        info.error = "offline"
        return info
    if not release or release.get("draft") or release.get("prerelease"):
        return info
    tag = str(release.get("tag_name", ""))
    info.latest = tag.removeprefix("v")
    info.update_available = is_newer(tag, current)
    info.url = str(release.get("html_url") or RELEASES_PAGE)
    info.notes = str(release.get("body") or "")[:4000]
    info.published_at = release.get("published_at")
    for asset in release.get("assets") or []:
        name = str(asset.get("name", ""))
        if name.endswith("-win64.zip"):
            info.download_url = asset.get("browser_download_url")
    return info


class UpdateChecker:
    """Caches the last answer so the UI can ask freely."""

    def __init__(self) -> None:
        self._last: UpdateInfo | None = None

    def get(self, force: bool = False) -> UpdateInfo:
        fresh = self._last and time.time() - self._last.checked_at < CACHE_SECONDS
        if force or not fresh or (self._last and self._last.error):
            self._last = check()
        assert self._last is not None
        return self._last
