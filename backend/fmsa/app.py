"""Entry point: start the local server and open the desktop window.

fmsa                 normal start (native window via Edge WebView2)
fmsa --browser       open in the default browser instead of a native window
fmsa --dev           API only on 127.0.0.1:8765 with token "dev" (for `npm run dev`)
"""

from __future__ import annotations

import argparse
import ctypes
import logging
import secrets
import socket
import sys
import threading
import time
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import uvicorn

from fmsa import __version__
from fmsa.config import SettingsStore
from fmsa.paths import APP_NAME, AppPaths
from fmsa.server import create_app

log = logging.getLogger("fmsa")

DEV_PORT = 8765
DEV_TOKEN = "dev"
WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"


def setup_logging(paths: AppPaths) -> None:
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            paths.logs_dir / "fmsa.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        ),
    ]
    if sys.stderr is not None:  # None in the windowed (no console) executable
        handlers.append(logging.StreamHandler())
    logging.captureWarnings(True)
    logging.basicConfig(
        level=logging.INFO,
        handlers=handlers,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def bind_socket(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_EXCLUSIVEADDRUSE if sys.platform == "win32" else socket.SO_REUSEADDR,
        1,
    )
    sock.bind(("127.0.0.1", port))
    return sock


class LocalServer:
    """Uvicorn running in a background thread on an already-bound loopback socket."""

    def __init__(self, app: object, sock: socket.socket) -> None:
        self.sock = sock
        self.port: int = sock.getsockname()[1]
        config = uvicorn.Config(app, log_config=None, access_log=False)  # type: ignore[arg-type]
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(
            target=self.server.run, kwargs={"sockets": [sock]}, daemon=True, name="fmsa-server"
        )

    def start(self, timeout: float = 15.0) -> None:
        self.thread.start()
        deadline = time.monotonic() + timeout
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("local server failed to start")
            time.sleep(0.05)

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


def message_box(text: str, title: str = APP_NAME) -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)  # MB_ICONINFORMATION
    else:
        print(text)


class DesktopApi:
    """Functions the frontend can call through `window.pywebview.api` (native window only)."""

    def __init__(self) -> None:
        self.window: Any = None

    def pick_save(self, folder: str = "") -> str | None:
        return self._pick(folder, "Football Manager save (*.fm)")

    def pick_career(self, folder: str = "") -> str | None:
        return self._pick(folder, "FMSaveAnalyst career (*.fmsa)")

    def pick_export_path(self, file_name: str) -> str | None:
        import webview

        dialog = getattr(getattr(webview, "FileDialog", None), "SAVE", None)
        if dialog is None:
            dialog = webview.SAVE_DIALOG  # type: ignore[attr-defined]
        kind = {".json": "JSON (*.json)", ".zip": "ZIP (*.zip)"}.get(
            Path(file_name).suffix.lower(), "CSV (*.csv)"
        )
        result = self.window.create_file_dialog(
            dialog, directory=str(Path.home() / "Documents"), save_filename=file_name,
            file_types=(kind,),
        )  # fmt: skip
        if not result:
            return None
        return str(result if isinstance(result, str) else result[0])

    def _pick(self, folder: str, file_type: str) -> str | None:
        import webview

        dialog = getattr(getattr(webview, "FileDialog", None), "OPEN", None)
        if dialog is None:
            dialog = webview.OPEN_DIALOG  # type: ignore[attr-defined]
        result = self.window.create_file_dialog(
            dialog, directory=folder or "", allow_multiple=False, file_types=(file_type,)
        )
        return str(result[0]) if result else None


def open_window(url: str) -> bool:
    """Show the UI in a native window. Returns False if WebView2 is unavailable."""
    try:
        import webview  # pywebview

        api = DesktopApi()
        api.window = webview.create_window(
            f"{APP_NAME} {__version__}",
            url,
            js_api=api,
            width=1440,
            height=900,
            min_size=(1024, 680),
            text_select=True,
        )
        webview.start(gui="edgechromium" if sys.platform == "win32" else None, private_mode=True)
        return True
    except Exception:
        log.exception("Native window unavailable, falling back to the browser")
        return False


def self_test(paths: AppPaths, save: str) -> int:
    """Verify that the packaged app has everything it needs. Result goes to the log file."""
    ok = True
    try:
        import fmsave
        import webview  # noqa: F401

        log.info("self-test: fmsave %s and pywebview import OK", fmsave.__version__)
        if save:
            with fmsave.open(save) as s:
                info = s.info
                clubs = len(s.clubs())
            log.info(
                "self-test: opened %s (%s %s, %s) clubs=%d",
                info.file_name,
                info.game,
                info.build,
                info.game_date,
                clubs,
            )
    except Exception:
        log.exception("self-test: import/open failed")
        ok = False
    index = paths.frontend_dir / "index.html"
    if not index.is_file():
        log.error("self-test: frontend missing at %s", index)
        ok = False
    try:
        token = secrets.token_urlsafe(8)
        server = LocalServer(create_app(paths, SettingsStore(paths), token), bind_socket(0))
        server.start()
        server.stop()
        log.info("self-test: local server OK")
    except Exception:
        log.exception("self-test: local server failed")
        ok = False
    log.info("self-test: %s", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fmsa", description=APP_NAME)
    parser.add_argument("--browser", action="store_true", help="open in the default browser")
    parser.add_argument("--dev", action="store_true", help="API only on port 8765, token 'dev'")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument(
        "--self-test",
        nargs="?",
        const="",
        metavar="SAVE",
        help="check the bundled components (optionally open SAVE) and exit",
    )
    args = parser.parse_args(argv)

    paths = AppPaths.resolve()
    paths.ensure()
    setup_logging(paths)
    log.info(
        "%s %s starting (portable=%s, data=%s)",
        APP_NAME,
        __version__,
        paths.portable,
        paths.data_dir,
    )
    if args.self_test is not None:
        return self_test(paths, args.self_test)

    store = SettingsStore(paths)
    token = DEV_TOKEN if args.dev else secrets.token_urlsafe(32)
    port = DEV_PORT if args.dev and not args.port else args.port
    server = LocalServer(create_app(paths, store, token), bind_socket(port))
    server.start()
    url = f"http://127.0.0.1:{server.port}/?t={token}"
    log.info("Server listening on 127.0.0.1:%s", server.port)

    try:
        if args.dev:
            print(
                f"API ready on http://127.0.0.1:{server.port} (token '{DEV_TOKEN}'). "
                "Ctrl+C to stop."
            )
            while server.thread.is_alive():
                time.sleep(0.5)
        elif args.browser or not open_window(url):
            webbrowser.open(url)
            note = (
                ""
                if args.browser
                else (
                    "Il componente Microsoft Edge WebView2 non è disponibile, quindi l'app è stata "
                    f"aperta nel browser.\nPuoi installarlo da {WEBVIEW2_URL}\n\n"
                )
            )
            message_box(
                f"{note}{APP_NAME} è aperto nel browser.\nPremi OK per chiudere l'applicazione."
            )
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        log.info("Stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
