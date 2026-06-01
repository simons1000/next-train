import io
import json
import os
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from unittest.mock import MagicMock, mock_open, patch

import pytest

import server
from server import Handler, load_config


# ── Helpers ────────────────────────────────────────────────────────────────────

SAMPLE_DEPARTURES = {
    "trainServices": [
        {
            "std": "10:58", "etd": "On time", "platform": "1",
            "operator": "South Western Railway",
            "destination": [{"locationName": "London Waterloo", "crs": "WAT"}],
        }
    ],
    "locationName": "Worcester Park",
    "crs": "WCP",
}


def make_handler(path='/api/departures'):
    """Return a Handler instance wired to a fake socket, without a real server."""
    sock = MagicMock()
    sock.makefile.return_value = io.BytesIO()
    handler = Handler.__new__(Handler)
    handler.path = path
    handler.headers = {}
    handler.rfile = io.BytesIO()
    buf = io.BytesIO()
    handler.wfile = buf
    handler.requestline = f'GET {path} HTTP/1.1'
    handler.request_version = 'HTTP/1.1'
    handler.command = 'GET'
    handler.request = sock
    handler.client_address = ('127.0.0.1', 0)
    handler.server = MagicMock()
    return handler, buf


def parse_response(buf):
    """Parse the raw HTTP response bytes written to buf."""
    buf.seek(0)
    raw = buf.read().decode()
    lines = raw.split('\r\n')
    status_line = lines[0]
    status_code = int(status_line.split(' ')[1])
    # find blank line separating headers from body
    blank = lines.index('')
    body_str = '\r\n'.join(lines[blank + 1:])
    try:
        body = json.loads(body_str)
    except json.JSONDecodeError:
        body = body_str
    return status_code, body


# ── load_config ────────────────────────────────────────────────────────────────

class TestLoadConfig:
    def test_reads_config_json(self, tmp_path):
        cfg = {"station": "WAT", "rows": 5}
        (tmp_path / "config.json").write_text(json.dumps(cfg))
        with patch("server.__file__", str(tmp_path / "server.py")):
            result = load_config()
        assert result == cfg

    def test_missing_file_raises(self, tmp_path):
        with patch("server.__file__", str(tmp_path / "server.py")):
            with pytest.raises(FileNotFoundError):
                load_config()


# ── URL construction ───────────────────────────────────────────────────────────

class TestUrlConstruction:
    """Verify the URLs built for the upstream request."""

    def _url_for(self, cfg_extra=None):
        cfg = {"station": "WCP", "api_key": "", "rows": 10}
        if cfg_extra:
            cfg.update(cfg_extra)
        captured = []
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(SAMPLE_DEPARTURES).encode()
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)

        def fake_urlopen(req, timeout):
            captured.append(req.full_url)
            return mock_response

        handler, _ = make_handler()
        with patch("server.load_config", return_value=cfg), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            handler.do_GET()

        return captured

    def test_basic_url(self):
        urls = self._url_for()
        assert urls == ["https://huxley2.azurewebsites.net/departures/WCP/10"]

    def test_filter_crs_included(self):
        urls = self._url_for({"filter_crs": "WAT"})
        assert urls == ["https://huxley2.azurewebsites.net/departures/WCP/to/WAT/10"]

    def test_custom_rows(self):
        urls = self._url_for({"rows": 5})
        assert urls == ["https://huxley2.azurewebsites.net/departures/WCP/5"]

    def test_no_access_token_in_url(self):
        urls = self._url_for({"api_key": "some-key"})
        assert "accessToken" not in urls[0]


# ── Success response ───────────────────────────────────────────────────────────

class TestDeparturesSuccess:
    def test_proxies_upstream_json(self):
        payload = json.dumps(SAMPLE_DEPARTURES).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = payload
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)

        handler, buf = make_handler()
        with patch("server.load_config", return_value={"station": "WCP", "rows": 10}), \
             patch("urllib.request.urlopen", return_value=mock_response):
            handler.do_GET()

        status, body = parse_response(buf)
        assert status == 200
        assert body["crs"] == "WCP"
        assert len(body["trainServices"]) == 1

    def test_content_type_is_json(self):
        payload = json.dumps(SAMPLE_DEPARTURES).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = payload
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)

        handler, buf = make_handler()
        with patch("server.load_config", return_value={"station": "WCP", "rows": 10}), \
             patch("urllib.request.urlopen", return_value=mock_response):
            handler.do_GET()

        buf.seek(0)
        raw = buf.read().decode()
        assert "Content-Type: application/json" in raw


# ── 404 fallback ───────────────────────────────────────────────────────────────

class TestFourOhFourFallback:
    def _make_http_error(self, code):
        return urllib.error.HTTPError(url="", code=code, msg=str(code), hdrs={}, fp=None)

    def test_retries_without_rows_on_404(self):
        payload = json.dumps(SAMPLE_DEPARTURES).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = payload
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)

        calls = []
        def fake_urlopen(req, timeout):
            calls.append(req.full_url)
            if len(calls) == 1:
                raise self._make_http_error(404)
            return mock_response

        handler, buf = make_handler()
        with patch("server.load_config", return_value={"station": "WCP", "rows": 10}), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            handler.do_GET()

        assert len(calls) == 2
        assert calls[0].endswith("/10")
        assert not calls[1].endswith("/10")
        status, body = parse_response(buf)
        assert status == 200

    def test_fallback_preserves_filter_crs(self):
        calls = []
        def fake_urlopen(req, timeout):
            calls.append(req.full_url)
            raise self._make_http_error(404)

        handler, buf = make_handler()
        with patch("server.load_config", return_value={"station": "WCP", "rows": 10, "filter_crs": "WAT"}), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            handler.do_GET()

        assert "/to/WAT" in calls[1]

    def test_non_404_does_not_retry(self):
        calls = []
        def fake_urlopen(req, timeout):
            calls.append(req.full_url)
            raise self._make_http_error(500)

        handler, buf = make_handler()
        with patch("server.load_config", return_value={"station": "WCP", "rows": 10}), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            handler.do_GET()

        assert len(calls) == 1
        status, body = parse_response(buf)
        assert status == 502
        assert body["error"] == "upstream_http"
        assert body["status"] == 500

    def test_fallback_failure_returns_502(self):
        def fake_urlopen(req, timeout):
            raise self._make_http_error(404)

        handler, buf = make_handler()
        with patch("server.load_config", return_value={"station": "WCP", "rows": 10}), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            handler.do_GET()

        status, body = parse_response(buf)
        assert status == 502
        assert body["error"] == "upstream_http"


# ── Generic error handling ─────────────────────────────────────────────────────

class TestErrorHandling:
    def test_network_error_returns_502(self):
        handler, buf = make_handler()
        with patch("server.load_config", return_value={"station": "WCP", "rows": 10}), \
             patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            handler.do_GET()

        status, body = parse_response(buf)
        assert status == 502
        assert body["error"] == "upstream_error"
        assert "timeout" in body["message"]

    def test_fallback_network_error_returns_502(self):
        calls = []
        def fake_urlopen(req, timeout):
            calls.append(req.full_url)
            if len(calls) == 1:
                raise urllib.error.HTTPError(url="", code=404, msg="", hdrs={}, fp=None)
            raise OSError("connection refused")

        handler, buf = make_handler()
        with patch("server.load_config", return_value={"station": "WCP", "rows": 10}), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            handler.do_GET()

        status, body = parse_response(buf)
        assert status == 502
        assert body["error"] == "upstream_error"

    def test_unknown_path_returns_404(self):
        handler, buf = make_handler(path='/not-a-thing')
        handler.do_GET()
        buf.seek(0)
        raw = buf.read().decode()
        assert raw.startswith("HTTP/1.0 404")


# ── Static file serving ────────────────────────────────────────────────────────

class TestFileServing:
    def test_serves_index_html(self, tmp_path):
        html = b"<html>hello</html>"
        (tmp_path / "index.html").write_bytes(html)

        handler, buf = make_handler(path='/')
        with patch("server.__file__", str(tmp_path / "server.py")):
            handler.do_GET()

        status, body = parse_response(buf)
        assert status == 200
        assert body == "<html>hello</html>"

    def test_missing_file_returns_404(self, tmp_path):
        handler, buf = make_handler(path='/')
        with patch("server.__file__", str(tmp_path / "server.py")):
            handler.do_GET()

        buf.seek(0)
        raw = buf.read().decode()
        assert raw.startswith("HTTP/1.0 404")
