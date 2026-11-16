"""Write the API's OpenAPI schema to frontend/src/lib/api/openapi.json (the frontend's typed contract).

    python scripts/export_openapi.py          # then, in frontend/: npm run gen:api

CI runs this and fails if the committed file differs, so a backend change that alters the API
contract can't be merged without the frontend types being regenerated (and type-checked) too.
"""
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# Settings must import; nothing connects to a database or signs a token here.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost:1/unused")
os.environ.setdefault("JWT_SECRET_KEY", "openapi-export-only-not-a-real-secret-0123456")

from app.main import app  # noqa: E402

target = ROOT / "frontend" / "src" / "lib" / "api" / "openapi.json"
target.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
print(f"wrote {target.relative_to(ROOT)} ({len(app.openapi()['paths'])} paths)")
