"""Tests for the local review HTTP server."""

import json
import threading
import time
from http.client import HTTPConnection
from unittest.mock import patch

from market_intel.core.server import ReviewHandler, start_server


def _mock_review():
    return {
        "ok": True,
        "command": "review",
        "data": {"window": "day", "sync": {"record_count": 100}},
        "meta": {"generated_at": "2026-06-10T16:00:00"},
        "errors": [],
    }


def _mock_html(payload, serve_mode=False):
    return "<html><body>复盘报告 count=%s</body></html>" % payload["data"]["sync"]["record_count"]


def test_handler_serves_html():
    from http.server import HTTPServer

    ReviewHandler.review_fn = _mock_review
    ReviewHandler.html_fn = _mock_html
    ReviewHandler._cached_html = ""
    ReviewHandler._cached_payload = {}

    server = HTTPServer(("127.0.0.1", 0), ReviewHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/")
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()
    thread.join(timeout=5)
    server.server_close()

    assert resp.status == 200
    assert "复盘报告" in body
    assert "count=100" in body
    assert "刷新复盘" in body


def test_handler_refresh_redirects():
    from http.server import HTTPServer

    call_count = [0]

    def counting_review():
        call_count[0] += 1
        return _mock_review()

    ReviewHandler.review_fn = counting_review
    ReviewHandler.html_fn = _mock_html
    ReviewHandler._cached_html = ""
    ReviewHandler._cached_payload = {}

    server = HTTPServer(("127.0.0.1", 0), ReviewHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/refresh")
    resp = conn.getresponse()
    conn.close()
    thread.join(timeout=5)
    server.server_close()

    assert resp.status == 302
    assert resp.getheader("Location") == "/"
    assert call_count[0] >= 1


def test_handler_serves_json_api():
    from http.server import HTTPServer

    ReviewHandler.review_fn = _mock_review
    ReviewHandler.html_fn = _mock_html
    ReviewHandler._cached_html = ""
    ReviewHandler._cached_payload = {}

    server = HTTPServer(("127.0.0.1", 0), ReviewHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/api/review")
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()
    thread.join(timeout=5)
    server.server_close()

    assert resp.status == 200
    data = json.loads(body)
    assert data["ok"] is True
    assert data["data"]["sync"]["record_count"] == 100


def test_handler_404_for_unknown():
    from http.server import HTTPServer

    ReviewHandler.review_fn = _mock_review
    ReviewHandler.html_fn = _mock_html
    ReviewHandler._cached_html = ""
    ReviewHandler._cached_payload = {}

    server = HTTPServer(("127.0.0.1", 0), ReviewHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/nonexistent")
    resp = conn.getresponse()
    conn.close()
    thread.join(timeout=5)
    server.server_close()

    assert resp.status == 404


def test_handler_no_cache_header():
    from http.server import HTTPServer

    ReviewHandler.review_fn = _mock_review
    ReviewHandler.html_fn = _mock_html
    ReviewHandler._cached_html = ""
    ReviewHandler._cached_payload = {}

    server = HTTPServer(("127.0.0.1", 0), ReviewHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/")
    resp = conn.getresponse()
    resp.read()
    conn.close()
    thread.join(timeout=5)
    server.server_close()

    assert resp.getheader("Cache-Control") == "no-cache"


def test_injected_refresh_button():
    ReviewHandler.review_fn = _mock_review
    ReviewHandler.html_fn = _mock_html
    ReviewHandler._cached_html = ""

    handler = ReviewHandler.__new__(ReviewHandler)
    html = "<html><body>test</body></html>"
    result = handler._inject_controls(html)

    assert "/refresh" in result
    assert "刷新复盘" in result
    assert "<body>" in result


def test_post_api_run_read_only_redirects():
    from http.server import HTTPServer
    from urllib.parse import urlencode

    call_count = [0]

    def counting_review():
        call_count[0] += 1
        return _mock_review()

    ReviewHandler.review_fn = counting_review
    ReviewHandler.html_fn = _mock_html
    ReviewHandler._cached_html = ""
    ReviewHandler._cached_payload = {}

    server = HTTPServer(("127.0.0.1", 0), ReviewHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    body = urlencode({"command": "market-intel review --no-sync --no-save"})
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", "/api/run", body=body,
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    conn.close()
    thread.join(timeout=5)
    server.server_close()

    assert resp.status == 302
    assert resp.getheader("Location") == "/"
    assert call_count[0] >= 1


def test_post_api_run_write_returns_403():
    from http.server import HTTPServer
    from urllib.parse import urlencode

    ReviewHandler.review_fn = _mock_review
    ReviewHandler.html_fn = _mock_html
    ReviewHandler._cached_html = ""
    ReviewHandler._cached_payload = {}

    server = HTTPServer(("127.0.0.1", 0), ReviewHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    body = urlencode({"command": "market-intel pool add SH600000"})
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", "/api/run", body=body,
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp_body = resp.read().decode("utf-8")
    conn.close()
    thread.join(timeout=5)
    server.server_close()

    assert resp.status == 403
    assert "写入操作需要在命令行执行" in resp_body
