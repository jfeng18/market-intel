"""Local HTTP server for the review HTML report."""

import json
import socket
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qs

from .agent import command_state_effect


class ReviewHandler(BaseHTTPRequestHandler):
    """Serve the HTML review report with a refresh mechanism."""

    review_fn: Optional[Callable[[], Dict[str, Any]]] = None
    html_fn: Optional[Callable[..., str]] = None
    _cached_html: str = ""
    _cached_payload: Dict[str, Any] = {}

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            self._serve_report()
        elif self.path == "/refresh":
            self._refresh_and_redirect()
        elif self.path == "/api/review":
            self._serve_json()
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/api/run":
            self._handle_run()
        else:
            self.send_error(404)

    def _handle_run(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        params = parse_qs(body)
        command = params.get("command", [""])[0]
        if not command:
            self.send_error(400)
            return
        effect = command_state_effect(command)
        if effect != "read_only":
            msg = "写入操作需要在命令行执行。".encode("utf-8")
            self._respond(403, "text/plain; charset=utf-8", msg)
            return
        self._do_refresh()
        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def _serve_report(self) -> None:
        if not self.__class__._cached_html:
            self._do_refresh()
        html = self._inject_controls(self.__class__._cached_html)
        self._respond(200, "text/html; charset=utf-8", html.encode("utf-8"))

    def _refresh_and_redirect(self) -> None:
        self._do_refresh()
        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def _serve_json(self) -> None:
        if not self.__class__._cached_payload:
            self._do_refresh()
        body = json.dumps(self.__class__._cached_payload, ensure_ascii=False, indent=2)
        self._respond(200, "application/json; charset=utf-8", body.encode("utf-8"))

    def _do_refresh(self) -> None:
        if self.__class__.review_fn and self.__class__.html_fn:
            payload = self.__class__.review_fn()
            self.__class__._cached_payload = payload
            self.__class__._cached_html = self.__class__.html_fn(payload, serve_mode=True)

    def _inject_controls(self, html: str) -> str:
        controls = """<div style="position:fixed;top:12px;right:12px;z-index:999">
<a href="/refresh" style="display:inline-block;padding:8px 16px;
background:var(--blue);color:var(--bg);border-radius:6px;
text-decoration:none;font-size:0.85em;font-weight:600">刷新复盘</a>
</div>"""
        return html.replace("<body>", "<body>\n" + controls, 1)

    def _respond(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


def start_server(
    review_fn: Callable[[], Dict[str, Any]],
    html_fn: Callable[..., str],
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
) -> None:
    """Start a local HTTP server serving the review report."""
    ReviewHandler.review_fn = review_fn
    ReviewHandler.html_fn = html_fn
    ReviewHandler._cached_html = ""
    ReviewHandler._cached_payload = {}

    server = HTTPServer((host, port), ReviewHandler)
    url = "http://127.0.0.1:%d" % port

    print("复盘工作台已启动: %s" % url)
    if host == "0.0.0.0":
        lan_ip = _get_lan_ip()
        if lan_ip:
            print("手机访问（同一 WiFi）: http://%s:%d" % (lan_ip, port))
    print("请保持此窗口打开。关闭将停止服务。")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        server.shutdown()


def _get_lan_ip() -> Optional[str]:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None
        server.shutdown()
