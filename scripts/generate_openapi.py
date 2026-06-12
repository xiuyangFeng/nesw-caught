#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OPENAPI_PATH = ROOT / "frontend" / "openapi.json"
GENERATED_PATH = ROOT / "frontend" / "src" / "types" / "generated.ts"


def export_openapi() -> dict:
    sys.path.insert(0, str(BACKEND))
    from app.main import app

    return app.openapi()


def write_openapi(payload: dict) -> None:
    OPENAPI_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def generate_typescript() -> None:
    subprocess.run(
        [
            "npx",
            "--yes",
            "openapi-typescript",
            str(OPENAPI_PATH),
            "-o",
            str(GENERATED_PATH),
        ],
        cwd=ROOT / "frontend",
        check=True,
    )


def main() -> None:
    payload = export_openapi()
    write_openapi(payload)
    generate_typescript()
    print(f"Wrote {OPENAPI_PATH.relative_to(ROOT)}")
    print(f"Wrote {GENERATED_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
