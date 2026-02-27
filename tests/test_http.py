"""
Tests for utils/http.py

All HTTP calls are mocked with unittest.mock — no real network requests made.

Covers:
  - get_headers()   — structure, User-Agent rotation, Accept-Encoding
  - polite_get()    — success, HTTP errors, retries, timeout, empty URL
"""
from unittest.mock import MagicMock, patch

import pytest
import requests

from utils.http import USER_AGENTS, get_headers, polite_get


# ── get_headers ───────────────────────────────────────────────────────────────

class TestGetHeaders:
    def test_returns_dict(self):
        assert isinstance(get_headers(), dict)

    def test_user_agent_present(self):
        headers = get_headers()
        assert "User-Agent" in headers

    def test_user_agent_is_known(self):
        # User-Agent must be one of the predefined strings
        headers = get_headers()
        assert headers["User-Agent"] in USER_AGENTS

    def test_no_brotli_in_accept_encoding(self):
        # 'br' must be absent — requests cannot decompress Brotli
        headers = get_headers()
        assert "br" not in headers.get("Accept-Encoding", "")

    def test_gzip_in_accept_encoding(self):
        headers = get_headers()
        assert "gzip" in headers["Accept-Encoding"]

    def test_extra_headers_merged(self):
        extra = {"X-Custom": "test-value"}
        headers = get_headers(extra=extra)
        assert headers["X-Custom"] == "test-value"

    def test_extra_headers_override(self):
        headers = get_headers(extra={"Accept-Language": "de-DE"})
        assert headers["Accept-Language"] == "de-DE"


# ── polite_get ────────────────────────────────────────────────────────────────

class TestPoliteGet:
    def test_empty_url_returns_none(self):
        assert polite_get("") is None

    def test_none_url_returns_none(self):
        assert polite_get(None) is None

    @patch("utils.http.requests.get")
    def test_successful_get_returns_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = polite_get("https://example.com/jobs")

        assert result is mock_resp
        mock_get.assert_called_once()

    @patch("utils.http.requests.get")
    def test_403_retries_and_returns_none(self, mock_get):
        error_resp = MagicMock()
        error_resp.status_code = 403
        http_err = requests.exceptions.HTTPError(response=error_resp)
        mock_get.side_effect = http_err

        with patch("utils.http.time.sleep"):  # don't actually sleep in tests
            result = polite_get("https://example.com/jobs", retries=1)

        assert result is None
        assert mock_get.call_count == 2  # initial + 1 retry

    @patch("utils.http.requests.get")
    def test_429_retries_and_returns_none(self, mock_get):
        error_resp = MagicMock()
        error_resp.status_code = 429
        http_err = requests.exceptions.HTTPError(response=error_resp)
        mock_get.side_effect = http_err

        with patch("utils.http.time.sleep"):
            result = polite_get("https://example.com/jobs", retries=1)

        assert result is None

    @patch("utils.http.requests.get")
    def test_timeout_retries_and_returns_none(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout()

        with patch("utils.http.time.sleep"):
            result = polite_get("https://example.com/jobs", retries=1)

        assert result is None
        assert mock_get.call_count == 2

    @patch("utils.http.requests.get")
    def test_network_error_returns_none(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("connection refused")

        result = polite_get("https://example.com/jobs", retries=0)

        assert result is None

    @patch("utils.http.requests.get")
    def test_success_after_retry(self, mock_get):
        """First call raises Timeout, second call succeeds."""
        good_resp = MagicMock()
        good_resp.raise_for_status.return_value = None

        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            good_resp,
        ]

        with patch("utils.http.time.sleep"):
            result = polite_get("https://example.com/jobs", retries=1)

        assert result is good_resp
        assert mock_get.call_count == 2
