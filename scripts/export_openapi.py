#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to frontend/openapi.json.

Usage (from repo root):
    conda run -n news-caught python scripts/export_openapi.py [output_path]

This only builds the FastAPI app object and serializes ``app.openapi()``.
It never starts the server and never touches the database (lifespan hooks
do not run on import).

The JSON is written with sorted keys and stable indentation so repeated
runs are byte-for-byte idempotent, which lets CI diff it for drift.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DEFAULT_OUTPUT = ROOT / "frontend" / "openapi.json"


def main() -> None:
    sys.path.insert(0, str(BACKEND))

    from app.main import create_app

    app = create_app()
    spec = app.openapi()

    output = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
