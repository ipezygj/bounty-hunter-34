import unittest
import sys
sys.path.insert(0, '/tmp/Kickama')
from tools.health_check import check_http_service
from unittest.mock import patch, MagicMock
import socket

class TestHealthCheck(unittest.TestCase):
    def test_empty_response(self):
        with patch('http.client.HTTPConnection') as m:
            r = MagicMock()
            r.status = 200
            r.headers.get.return_value = ""
            r.read.return_value = b""
            m.return_value.getresponse.return_value = r
            s, d, c = check_http_service("localhost", 8080, "/health", 5)
            assert s == "CRITICAL"
    
    def test_valid_response(self):
        with patch('http.client.HTTPConnection') as m:
            r = MagicMock()
            r.status = 200
            r.headers.get.return_value = "application/json"
            r.read.return_value = b'{"ok":true}'
            m.return_value.getresponse.return_value = r
            s, d, c = check_http_service("localhost", 8080, "/health", 5)
            assert s == "OK"
    
    def test_timeout(self):
        with patch('http.client.HTTPConnection') as m:
            m.side_effect = socket.timeout()
            s, d, c = check_http_service("localhost", 8080, "/health", 5)
            assert s == "CRITICAL"

if __name__ == '__main__':
    unittest.main()
