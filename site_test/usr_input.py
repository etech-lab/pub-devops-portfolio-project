# usr_input.py

import argparse
import csv
import sys
from typing import List, Iterator, TextIO


class UserInput:
    """Class for handling all user input related to URL testing.

    This class preserves the user's original API while fixing a couple of
    issues and improving file input support:
    - usr_cli_input() remains a thin wrapper that returns parsed args.
    - usr_file_input() now accepts comma-separated values, newline values,
    and '-' for stdin.
    """

    def usr_cli_input(self) -> argparse.Namespace:
        """Return parsed CLI arguments.

        Note: the parser accepts one or more URLs as positional arguments
        or an input file via -f/--input-file.
        """

        parser = argparse.ArgumentParser(
            prog="url_test", description="Test URL reachability"
        )
        parser.add_argument(
            "-f",
            "--input-file",
            help="Path to a file containing URLs (use '-' for stdin).",
            metavar="FILE",
            type=str,
        )
        parser.add_argument(
            "urls",
            help="One or more URLs to test (space separated).",
            nargs="*",
            type=str,
            default=[],
        )
        return parser.parse_args()

    def _iter_values_from_file(self, f: TextIO) -> Iterator[str]:
        """Yield non-empty, stripped values from a file-like object.

        Skip comment lines that start with #. Parse each non-comment line
        with csv.reader so comma-separated and newline-separated values
        are handled uniformly.
        """

        for raw in f:
            raw_strip = raw.strip()
            if not raw_strip:
                continue
            # ignore whole-line comments
            if raw_strip.startswith("#"):
                continue
            # parse the (non-comment) line as CSV to support commas
            for row in csv.reader([raw_strip]):
                for field in row:
                    token = field.strip()
                    if token:
                        yield token

    def usr_file_input(self, path: str) -> List[str]:
        """Read URLs from path and return a list of strings.

        - If path is '-', read from stdin.
        - Supports comma-separated values and newline-separated values.
        """

        if path == "-":
            return list(self._iter_values_from_file(sys.stdin))

        with open(path, "r", encoding="utf-8") as fh:
            return list(self._iter_values_from_file(fh))
