#!/usr/bin/env python3
"""
Unit tests for the health check tool.
Tests for empty response, malformed JSON, valid response, and HTTP failures.
"""

import json
import socket
import unittest
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import time
import sys
from pathlib import Path

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from health_check import check_http_service


class EmptyResponseHandler(BaseHTTPRequestHandler):
    """Mock HTTP server that returns empty 200 response."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"")  # Empty response

    def log_message(self, format, *args):
        pass  # Suppress logging


class MalformedJsonHandler(BaseHTTPRequestHandler):
    """Mock HTTP server that returns malformed JSON."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"')  # Missing closing brace

    def log_message(self, format, *args):
        pass  # Suppress logging


class ValidJsonHandler(BaseHTTPRequestHandler):
    """Mock HTTP server that returns valid JSON."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = json.dumps({"status": "ok", "uptime_seconds": 3600})
        self.wfile.write(response.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Suppress logging


class HttpErrorHandler(BaseHTTPRequestHandler):
    """Mock HTTP server that returns 500 error."""

    def do_GET(self):
        self.send_response(500)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Internal Server Error")

    def log_message(self, format, *args):
        pass  # Suppress logging


class HttpWarningHandler(BaseHTTPRequestHandler):
    """Mock HTTP server that returns 400 error."""

    def do_GET(self):
        self.send_response(400)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bad Request")

    def log_message(self, format, *args):
        pass  # Suppress logging


class HealthCheckTestCase(unittest.TestCase):
    """Base test case that manages mock servers."""

    server_threads = []

    @classmethod
    def start_mock_server(cls, handler_class, port):
        """Start a mock HTTP server in a background thread."""
        server = HTTPServer(("127.0.0.1", port), handler_class)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        cls.server_threads.append((server, thread))
        time.sleep(0.2)  # Give server time to start
        return server

    @classmethod
    def tearDownClass(cls):
        """Shut down all mock servers."""
        for server, thread in cls.server_threads:
            server.shutdown()


class TestHealthCheckEmptyResponse(HealthCheckTestCase):
    """Test health check with empty response."""

    @classmethod
    def setUpClass(cls):
        cls.port = 18080
        cls.start_mock_server(EmptyResponseHandler, cls.port)

    def test_empty_200_response_is_critical(self):
        """Empty response with 200 status should be reported as CRITICAL."""
        status, detail, code = check_http_service("127.0.0.1", self.port, "/health", 5)
        self.assertEqual(status, "CRITICAL")
        self.assertIn("empty", detail.lower())
        self.assertEqual(code, 200)


class TestHealthCheckMalformedJson(HealthCheckTestCase):
    """Test health check with malformed JSON."""

    @classmethod
    def setUpClass(cls):
        cls.port = 18081
        cls.start_mock_server(MalformedJsonHandler, cls.port)

    def test_malformed_json_is_critical(self):
        """Malformed JSON response should be reported as CRITICAL."""
        status, detail, code = check_http_service("127.0.0.1", self.port, "/health", 5)
        self.assertEqual(status, "CRITICAL")
        self.assertIn("malformed", detail.lower())
        self.assertEqual(code, 200)


class TestHealthCheckValidResponse(HealthCheckTestCase):
    """Test health check with valid response."""

    @classmethod
    def setUpClass(cls):
        cls.port = 18082
        cls.start_mock_server(ValidJsonHandler, cls.port)

    def test_valid_json_response_is_ok(self):
        """Valid JSON response with 200 status should be reported as OK."""
        status, detail, code = check_http_service("127.0.0.1", self.port, "/health", 5)
        self.assertEqual(status, "OK")
        self.assertIn("200", detail)
        self.assertEqual(code, 200)


class TestHealthCheckHttpError(HealthCheckTestCase):
    """Test health check with HTTP 500 error."""

    @classmethod
    def setUpClass(cls):
        cls.port = 18083
        cls.start_mock_server(HttpErrorHandler, cls.port)

    def test_http_500_is_critical(self):
        """HTTP 500 error should be reported as CRITICAL."""
        status, detail, code = check_http_service("127.0.0.1", self.port, "/health", 5)
        self.assertEqual(status, "CRITICAL")
        self.assertIn("500", detail)
        self.assertEqual(code, 500)


class TestHealthCheckHttpWarning(HealthCheckTestCase):
    """Test health check with HTTP 400 error."""

    @classmethod
    def setUpClass(cls):
        cls.port = 18084
        cls.start_mock_server(HttpWarningHandler, cls.port)

    def test_http_400_is_warning(self):
        """HTTP 400 error should be reported as WARNING."""
        status, detail, code = check_http_service("127.0.0.1", self.port, "/health", 5)
        self.assertEqual(status, "WARNING")
        self.assertIn("400", detail)
        self.assertEqual(code, 400)


class TestHealthCheckConnectionFailure(unittest.TestCase):
    """Test health check with connection failures."""

    def test_connection_refused_is_critical(self):
        """Connection refused or timeout should be reported as CRITICAL."""
        status, detail, code = check_http_service("127.0.0.1", 19999, "/health", 1)
        self.assertEqual(status, "CRITICAL")
        # On Windows, timeout may occur before connection refused
        self.assertTrue("refused" in detail.lower() or "timeout" in detail.lower())
        self.assertEqual(code, 0)

    def test_timeout_is_critical(self):
        """Connection timeout should be reported as CRITICAL."""
        # Use a non-routable IP that will timeout
        status, detail, code = check_http_service("192.0.2.1", 80, "/health", 1)
        self.assertEqual(status, "CRITICAL")
        self.assertTrue("timeout" in detail.lower() or "error" in detail.lower())
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
