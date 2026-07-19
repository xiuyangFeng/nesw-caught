#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to frontend/openapi.json.

Usage (from repo root):
    conda run -n news-caught python scripts/export_openapi.py [output_path]
    conda run -n news-caught python scripts/export_openapi.py --check

This only builds the FastAPI app object and serializes ``app.openapi()``.
It never starts the server and never touches the database (lifespan hooks
do not run on import).

The JSON is written with sorted keys and stable indentation so repeated
runs are byte-for-byte idempotent, which lets CI diff it for drift.

``--check`` mode does not overwrite ``frontend/openapi.json``. Instead it
regenerates the schema in memory, compares it against the committed file,
and exits non-zero if they differ. This is meant to catch the case where a
backend route/schema change wasn't followed by re-running the exporter, so
the frontend's ``frontend/openapi.json`` silently drifts from the actual
backend contract.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DEFAULT_OUTPUT = ROOT / "frontend" / "openapi.json"


def build_schema_text() -> str:
    """Build the FastAPI app and return the serialized OpenAPI schema text."""
    sys.path.insert(0, str(BACKEND))

    from app.main import create_app

    app = create_app()
    spec = app.openapi()
    return json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Path to write the exported schema to (ignored with --check).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Do not write any file. Regenerate the schema and diff it against "
            "frontend/openapi.json, exiting non-zero if they differ."
        ),
    )
    return parser.parse_args(argv)


def run_check() -> int:
    fresh_text = build_schema_text()

    if not DEFAULT_OUTPUT.exists():
        print(
            f"error: {DEFAULT_OUTPUT} does not exist. Run "
            "`python scripts/export_openapi.py` to create it.",
            file=sys.stderr,
        )
        return 1

    current_text = DEFAULT_OUTPUT.read_text(encoding="utf-8")

    if fresh_text == current_text:
        print(f"OK: {DEFAULT_OUTPUT} matches the current backend OpenAPI schema.")
        return 0

    print(
        f"error: {DEFAULT_OUTPUT} is out of date with the backend OpenAPI schema.\n"
        "Backend routes/schemas changed but the exported spec was not "
        "regenerated. Run:\n"
        "    conda run -n news-caught python scripts/export_openapi.py\n"
        "and commit the updated frontend/openapi.json.",
        file=sys.stderr,
    )
    return 1


def run_export(output_arg: str | None) -> int:
    output = Path(output_arg).resolve() if output_arg else DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_schema_text(), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


def main() -> None:
    args = parse_args(sys.argv[1:])

    if args.check:
        if args.output is not None:
            print("error: --check cannot be combined with an output path", file=sys.stderr)
            sys.exit(2)
        sys.exit(run_check())

    sys.exit(run_export(args.output))


if __name__ == "__main__":
    main()
