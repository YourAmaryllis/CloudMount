from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import api, capabilities, hosts, mounts  # noqa: E402


def _json_response(handler: BaseHTTPRequestHandler, code: int, data: Any) -> None:
    body = json.dumps(data).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    n = int(handler.headers.get("Content-Length") or 0)
    if n <= 0:
        return {}
    raw = handler.rfile.read(n)
    return json.loads(raw.decode() or "{}")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        # quieter
        pass

    def do_GET(self) -> None:
        u = urlparse(self.path)
        path = u.path
        if path in ("/", "/index.html"):
            self._static("index.html", "text/html")
            return
        if path.startswith("/static/"):
            name = path[len("/static/") :]
            ctype = {
                ".js": "application/javascript",
                ".css": "text/css",
                ".html": "text/html",
                ".svg": "image/svg+xml",
            }.get(Path(name).suffix, "application/octet-stream")
            self._static(name, ctype)
            return
        if path == "/api/status":
            _json_response(self, 200, api.status())
            return
        if path == "/api/capabilities":
            _json_response(self, 200, capabilities.report())
            return
        if path == "/api/setup":
            _json_response(self, 200, api.setup())
            return
        _json_response(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        u = urlparse(self.path)
        path = u.path
        try:
            body = _read_json(self)
        except Exception as e:
            _json_response(self, 400, {"ok": False, "error": f"bad json: {e}"})
            return
        try:
            if path == "/api/prefs":
                _json_response(self, 200, {"ok": True, "prefs": api.set_prefs(**body)})
                return
            if path == "/api/host":
                h = hosts.upsert_host(
                    host_id=body.get("id"),
                    name=body["name"],
                    type_=body.get("type") or "s3",
                    provider=body.get("provider") or "Wasabi",
                    endpoint=body.get("endpoint") or "https://s3.us-east-1.wasabisys.com",
                    region=body.get("region") or "us-east-1",
                    access_key=body.get("access_key"),
                    secret_key=body.get("secret_key"),
                )
                _json_response(self, 200, {"ok": True, "host": h})
                return
            if path == "/api/host/delete":
                hosts.delete_host(body["id"])
                _json_response(self, 200, {"ok": True})
                return
            if path == "/api/host/test":
                _json_response(self, 200, hosts.test_host(body["id"]))
                return
            if path == "/api/host/lsd":
                _json_response(
                    self,
                    200,
                    hosts.list_remote_paths(body["id"], body.get("prefix") or ""),
                )
                return
            if path == "/api/mount":
                m = mounts.upsert_mount(
                    mount_id=body.get("id"),
                    label=body["label"],
                    host_id=body["host_id"],
                    remote_path=body["remote_path"],
                    path=body["path"],
                    mount_kind=body.get("mount_kind") or "nfs",
                    vfs_cache_mode=body.get("vfs_cache_mode") or "full",
                )
                _json_response(self, 200, {"ok": True, "mount": m})
                return
            if path == "/api/mount/delete":
                mounts.delete_mount(body["id"])
                _json_response(self, 200, {"ok": True})
                return
            if path == "/api/mount/up":
                _json_response(self, 200, mounts.mount(body["id"]))
                return
            if path == "/api/mount/down":
                _json_response(self, 200, mounts.unmount(body["id"]))
                return
            if path == "/api/mount/all-up":
                _json_response(self, 200, {"ok": True, "results": mounts.mount_all()})
                return
            if path == "/api/mount/all-down":
                _json_response(self, 200, {"ok": True, "results": mounts.unmount_all()})
                return
            if path == "/api/mount/bulk":
                # body: host_id, remote_paths[], local_root, mount_kind, vfs_cache_mode, label_from
                r = mounts.bulk_add_from_paths(
                    host_id=body["host_id"],
                    remote_paths=list(body.get("remote_paths") or []),
                    local_root=body.get("local_root") or "~",
                    mount_kind=body.get("mount_kind") or "nfs",
                    vfs_cache_mode=body.get("vfs_cache_mode") or "full",
                    label_from=body.get("label_from") or "basename",
                )
                _json_response(self, 200, r)
                return
            if path == "/api/macfuse/help":
                _json_response(self, 200, capabilities.help_install_macfuse(True))
                return
            if path == "/api/macfuse/brew":
                _json_response(self, 200, capabilities.try_brew_install_macfuse())
                return
            _json_response(self, 404, {"ok": False, "error": "not found"})
        except Exception as e:
            _json_response(self, 400, {"ok": False, "error": str(e)})

    def _static(self, name: str, ctype: str) -> None:
        # prevent path escape
        name = Path(name).name if "/" not in name and "\\" not in name else name.replace("..", "")
        f = STATIC / name
        if not f.is_file():
            # also allow index only from STATIC root
            f = STATIC / Path(name).name
        if not f.is_file():
            self.send_error(404)
            return
        data = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_server(port: int = 8765, open_browser: bool = True) -> None:
    api.setup()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"CloudMount UI: {url}", flush=True)
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
