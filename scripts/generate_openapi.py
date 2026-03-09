"""Generate OpenAPI schema JSON from the FastAPI app."""

import json
from pathlib import Path

from agentaudit_api.main import create_app

app = create_app()
schema = app.openapi()

out = Path(__file__).resolve().parent.parent / "docs" / "api-reference" / "openapi.json"
out.write_text(json.dumps(schema, indent=2) + "\n")
print(f"OpenAPI schema written to {out}")
