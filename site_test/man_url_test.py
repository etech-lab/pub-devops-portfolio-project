"""Manual URL test runner (reusable) for development and manual testing.

Provides run_cli(argv=None) which can be called from other modules (e.g. a
future user-input module) or executed as a script.
"""

from typing import Dict, Optional

from .url_test import URLTester, HTTPHeadParser


def _print_headers(h: Dict[str, Optional[str]]) -> None:
    for k in ("Date", "Server", "Content-Type", "Content-Length"):
        print(f"{k}: {h.get(k)!s}")


def run_cli(argv=None):
    import sys

    if argv is None:
        argv = sys.argv

    if len(argv) < 2:
        print("Usage: python -m site_test.man_url_test <url>")
        return 2

    test_url = argv[1]
    print(f"Checking reachability for: {test_url}")
    try:
        reachable = URLTester.check_is_reachable(test_url)
        print("Reachable:", reachable)
    except Exception as e:
        print("Reachability check failed:", e)

    print("\nHEAD headers:")
    try:
        headers = HTTPHeadParser.fetch_from_url(test_url)
        _print_headers(headers)
    except Exception as e:
        print("HEAD request failed:", e)

    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(run_cli(sys.argv))
