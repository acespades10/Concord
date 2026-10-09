import json
from pathlib import Path

from app.main import app

if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / "openapi.json"
    path.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path}")
