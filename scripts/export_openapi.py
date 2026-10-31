"""Print the FastAPI OpenAPI schema as stable JSON (used to generate the TS types)."""

import json
import sys

from app.main import create_app

json.dump(create_app().openapi(), sys.stdout, indent=2, sort_keys=True)
sys.stdout.write("\n")
