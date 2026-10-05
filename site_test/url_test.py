# url_test.py
# stdlib
from http.client import HTTPConnection
from typing import Dict, Optional
from urllib.parse import urlparse


class URLTester:
    """Utilities for basic URL reachability checks."""

    @staticmethod
    def check_is_reachable(url: str, timeout: int = 2) -> bool:
        """If site is reachable, return True. Otherwise raise the last exception.

        This preserves the original behavior of trying common ports (80, 443),
        but ensures both ports are attempted before raising.
        """
        error: Exception = Exception("unknown error")
        parser = urlparse(url)
        host = parser.netloc or parser.path.split("/")[0]
        for port in (80, 443):
            connection = HTTPConnection(host=host, port=port, timeout=timeout)
            try:
                connection.request("HEAD", parser.path or "/")
                return True
            except Exception as err:
                error = err
            finally:
                try:
                    connection.close()
                except Exception:
                    pass
        raise error


class HTTPHeadParser:
    """Fetch and parse basic headers from a HEAD request.

    Methods return a dict with keys: 'Date', 'Server', 'Content-Type', 'Content-Length'.
    Values are strings or None when the header is not present.
    """

    @staticmethod
    def fetch_headers(
        host: str, port: int = 80, path: str = "/", timeout: int = 2
    ) -> Dict[str, Optional[str]]:
        conn = HTTPConnection(host=host, port=port, timeout=timeout)
        try:
            conn.request("HEAD", path)
            resp = conn.getresponse()
            # http.client.HTTPResponse provides getheader
            headers = {
                "Status-Code": resp.status,
                "Date": resp.getheader("Date"),
                "Server": resp.getheader("Server"),
                "Content-Type": resp.getheader("Content-Type"),
                "Content-Length": resp.getheader("Content-Length"),
                "Last-Modified": resp.getheader("Last-Modified"),
            }
            return headers
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def fetch_from_url(url: str, timeout: int = 2) -> Dict[str, Optional[str]]:
        parser = urlparse(url)
        host = parser.netloc or parser.path.split("/")[0]
        port = parser.port or (80 if parser.scheme != "https" else 443)
        path = parser.path or "/"
        return HTTPHeadParser.fetch_headers(
            host=host, port=port, path=path, timeout=timeout
        )
