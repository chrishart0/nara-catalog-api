from __future__ import annotations

import os
from pathlib import Path

DEFAULT_SECRET_FILE = Path.home() / ".hermes/secrets/nara.env"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_api_key(secret_file: str | None = None, project_dir: Path | None = None) -> tuple[str | None, str]:
    if os.environ.get("NARA_API_KEY"):
        return os.environ["NARA_API_KEY"], "environment:NARA_API_KEY"

    if secret_file:
        path = Path(secret_file).expanduser()
        values = load_env_file(path)
        if values.get("NARA_API_KEY"):
            return values["NARA_API_KEY"], str(path)
        return None, str(path)

    candidates = []
    if project_dir:
        candidates.append(project_dir / ".env")
    candidates.append(DEFAULT_SECRET_FILE)
    for candidate in candidates:
        values = load_env_file(candidate)
        if values.get("NARA_API_KEY"):
            return values["NARA_API_KEY"], str(candidate)
    return None, str(DEFAULT_SECRET_FILE)
