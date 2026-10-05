"""CLI entrypoint for site_test.

Runs as an interactive daemon: shows a banner on launch, then loops
waiting for user input.  A DB connection is opened once and held for
the life of the session.

Non-interactive / scripted mode is still supported: if URL arguments or
-f/--input-file are passed on the command line the app runs the tests
and exits normally (exit code 0 on success, 2 on error).
"""

from typing import Dict, Optional
import argparse
import sys
import asyncio

from .usr_input import UserInput
from .url_test import URLTester, HTTPHeadParser
from . import rds_connection


# ---------------------------------------------------------------------------
# Banner & UI helpers
# ---------------------------------------------------------------------------

BANNER = """\
╔══════════════════════════════════════════════════════════╗
║                  WebsiteTester  v1.0                     ║
╠══════════════════════════════════════════════════════════╣
║  Tests one or more URLs for reachability, collects       ║
║  HTTP HEAD headers, and stores every result in a         ║
║  PostgreSQL database.                                    ║
║                                                          ║
║  Input options                                           ║
║    [1]  Enter one or more URLs                           ║
║         (separate multiple URLs with a space)            ║
║    [2]  Provide a file path containing URLs              ║
║         (one per line, or comma-separated)               ║
║    [q]  Quit                                             ║
╚══════════════════════════════════════════════════════════╝"""

_SEP = "─" * 60


def _print_sep() -> None:
    print(_SEP)


# ---------------------------------------------------------------------------
# Async test runner (shared by both interactive and non-interactive modes)
# ---------------------------------------------------------------------------


async def _run_one(idx: int, u: str, conn) -> tuple:
    lines = [f"Results for: {u}"]
    reachable = False
    headers: Dict[str, Optional[str]] = {}

    try:
        reachable = await asyncio.to_thread(URLTester.check_is_reachable, u)
        lines.append(f"  Reachable    : {reachable}")
    except Exception as e:
        lines.append(f"  Reachable    : False  ({e})")

    lines.append("  HEAD headers :")
    try:
        headers = await asyncio.to_thread(HTTPHeadParser.fetch_from_url, u)
        for k in ("Status-Code", "Date", "Server", "Content-Type", "Content-Length"):
            lines.append(f"    {k}: {headers.get(k)!s}")
    except Exception as e:
        lines.append(f"    HEAD request failed: {e}")

    try:
        await asyncio.to_thread(
            rds_connection.save_test_result, conn, u, reachable, headers
        )
        lines.append("  ✓ Result saved to database")
    except Exception as e:
        lines.append(f"  ✗ Database save failed: {e}")

    return idx, "\n".join(lines)


async def _run_all(url_list, conn) -> None:
    tasks = [asyncio.create_task(_run_one(i, u, conn)) for i, u in enumerate(url_list)]
    results = await asyncio.gather(*tasks)
    for _idx, out in sorted(results, key=lambda x: x[0]):
        print("\n" + out)


def _test_urls(urls: list, conn) -> None:
    """Synchronous wrapper used by both modes."""
    _print_sep()
    asyncio.run(_run_all(urls, conn))
    _print_sep()


# ---------------------------------------------------------------------------
# Interactive daemon loop
# ---------------------------------------------------------------------------


def _interactive_loop(conn) -> None:
    """Run the interactive prompt until the user chooses to quit."""
    ui = UserInput()
    print(BANNER)

    while True:
        print("\nSelect an option  [1] Single URL   [2] File   [q] Quit")
        try:
            choice = input("> ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if choice == "1":
            try:
                raw = input("Enter URL(s) — separate multiple with a space: ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                continue
            urls = raw.split()
            if urls:
                _test_urls(urls, conn)
            else:
                print("No URL(s) entered.")

        elif choice == "2":
            try:
                path = input("Enter file path: ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                continue
            if not path:
                print("No path entered.")
                continue
            try:
                urls = ui.usr_file_input(path)
            except Exception as e:
                print(f"Error reading file: {e}")
                continue
            if urls:
                _test_urls(urls, conn)
            else:
                print("No URLs found in file.")

        elif choice in ("q", "quit", "exit", "3"):
            print("Goodbye.")
            break

        else:
            print("Invalid option — enter 1, 2, or q.")


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    """Entry point.

    Interactive (daemon) mode — no CLI args
    ----------------------------------------
    Shows the banner and enters the prompt loop.  The process stays alive
    until the user types 'q'.  Suitable for use as the container ENTRYPOINT.

    Non-interactive mode — CLI args present
    ----------------------------------------
    Accepts -f/--input-file or positional URLs, runs the tests, and exits.
    """

    # Decide mode based on whether the caller passed args (or sys.argv has any)
    cli_argv = argv if argv is not None else sys.argv[1:]
    interactive = len(cli_argv) == 0

    # ── Non-interactive path ──────────────────────────────────────────────
    if not interactive:
        ui = UserInput()
        args = ui.usr_cli_input()

        urls = []
        if getattr(args, "input_file", None):
            try:
                urls = ui.usr_file_input(args.input_file)
            except Exception as e:
                print("Failed to read input file:", e)
                return 2
        else:
            urls = list(getattr(args, "urls", []) or [])

        if not urls:
            parser = argparse.ArgumentParser(
                prog="site_test", description="Test URL reachability"
            )
            parser.add_argument(
                "-f",
                "--input-file",
                help="File containing URLs (use '-' for stdin).",
                metavar="FILE",
            )
            parser.add_argument(
                "urls",
                nargs="*",
                help="One or more URLs to test.",
            )
            parser.print_help()
            return 2

        try:
            conn = rds_connection.get_connection()
        except Exception as e:
            print(f"Database connection failed: {e}")
            return 2

        _test_urls(urls, conn)
        conn.close()
        return 0

    # ── Interactive / daemon path ─────────────────────────────────────────
    print("Connecting to database…", end=" ", flush=True)
    try:
        conn = rds_connection.get_connection()
        print("OK")
    except Exception as e:
        print(f"FAILED\nDatabase connection failed: {e}")
        return 2

    try:
        _interactive_loop(conn)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
