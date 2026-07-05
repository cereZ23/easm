"""
Unit tests for the Katana output parser and endpoint classifier.

These are pure-logic tests (no DB / no external tools) covering the parsing and
classification used by app.tasks.enrichment.run_katana.
"""

import json

from app.tasks.enrichment import parse_katana_line, _classify_endpoint


class TestParseKatanaLine:
    def test_api_endpoint_with_query_params(self):
        line = json.dumps({
            "request": {"method": "GET", "endpoint": "https://acme.com/api/v1/users?id=1", "tag": "a"},
            "response": {"status_code": 200, "content_length": 50,
                         "headers": {"content_type": "application/json; charset=utf-8"}},
        })
        ep = parse_katana_line(line, "https://acme.com", "acme.com")
        assert ep is not None
        assert ep["url"] == "https://acme.com/api/v1/users?id=1"
        assert ep["method"] == "GET"
        assert ep["path"] == "/api/v1/users"
        assert ep["query_params"] == {"id": "1"}
        assert ep["is_api"] is True
        assert ep["endpoint_type"] == "api"
        assert ep["is_external"] is False
        assert ep["content_type"] == "application/json"  # charset stripped

    def test_form_endpoint(self):
        line = json.dumps({
            "request": {"method": "POST", "endpoint": "https://acme.com/login", "tag": "form"},
            "response": {"status_code": 200},
        })
        ep = parse_katana_line(line, "https://acme.com", "acme.com")
        assert ep["endpoint_type"] == "form"
        assert ep["method"] == "POST"
        assert ep["is_api"] is False

    def test_external_link(self):
        line = json.dumps({
            "request": {"method": "GET", "endpoint": "https://cdn.other.com/app.js"},
            "response": {"status_code": 200},
        })
        ep = parse_katana_line(line, "https://acme.com", "acme.com")
        assert ep["is_external"] is True
        assert ep["endpoint_type"] == "external"

    def test_subdomain_is_internal(self):
        line = "https://sub.acme.com/dashboard"
        ep = parse_katana_line(line, "https://acme.com", "acme.com")
        assert ep["is_external"] is False
        assert ep["endpoint_type"] == "static"

    def test_static_file(self):
        ep = parse_katana_line("https://acme.com/static/logo.png", "https://acme.com", "acme.com")
        assert ep["endpoint_type"] == "file"

    def test_redirect(self):
        line = json.dumps({
            "request": {"method": "GET", "endpoint": "https://acme.com/home"},
            "response": {"status_code": 301},
        })
        ep = parse_katana_line(line, "https://acme.com", "acme.com")
        assert ep["endpoint_type"] == "redirect"

    def test_plain_url_line(self):
        ep = parse_katana_line("https://acme.com/about", "https://acme.com", "acme.com")
        assert ep is not None
        assert ep["url"] == "https://acme.com/about"
        assert ep["method"] == "GET"

    def test_non_json_non_url_skipped(self):
        assert parse_katana_line("not a url at all", "https://acme.com", "acme.com") is None

    def test_non_http_scheme_skipped(self):
        assert parse_katana_line("ftp://acme.com/file", "https://acme.com", "acme.com") is None

    def test_malformed_json_skipped(self):
        assert parse_katana_line('{"broken": ', "https://acme.com", "acme.com") is None


class TestClassifyEndpoint:
    def test_json_content_type_is_api(self):
        etype, is_api = _classify_endpoint(
            path="/data", query_params=None, tag=None,
            status_code=200, content_type="application/json", is_external=False,
        )
        assert (etype, is_api) == ("api", True)

    def test_query_params_makes_api(self):
        etype, is_api = _classify_endpoint(
            path="/search", query_params={"q": "x"}, tag=None,
            status_code=200, content_type="text/html", is_external=False,
        )
        assert is_api is True

    def test_external_beats_api(self):
        etype, is_api = _classify_endpoint(
            path="/api/v1/x", query_params={"a": "1"}, tag=None,
            status_code=200, content_type="application/json", is_external=True,
        )
        assert etype == "external"
        assert is_api is False
