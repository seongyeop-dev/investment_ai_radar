from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path

ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
OPENDART_KEY = re.compile(r"^[A-Za-z0-9]{40}$")
CONTACT_EMAIL = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def normalize_local_value(value: str) -> str:
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        normalized = normalized[1:-1].strip()
    return normalized


def valid_opendart_key(value: str) -> bool:
    return bool(OPENDART_KEY.fullmatch(normalize_local_value(value)))


def valid_contact_email(value: str) -> bool:
    return bool(CONTACT_EMAIL.fullmatch(normalize_local_value(value)))


def parse_local_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError("local environment file contains an invalid line")
        name, value = line.split("=", 1)
        name = name.strip()
        if not ENV_NAME.fullmatch(name):
            raise ValueError("local environment file contains an invalid name")
        values[name] = normalize_local_value(value)
    return values


def load_local_environment(
    base: Mapping[str, str] | None = None,
    *,
    project_root: Path | None = None,
) -> dict[str, str]:
    environment = dict(base if base is not None else os.environ)
    root = project_root or Path(__file__).resolve().parents[3]
    candidates = (root / ".env.local", root / "server" / ".env.local")
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return environment
    try:
        local_values = parse_local_env(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ValueError("local environment file could not be read") from exc
    for name, value in local_values.items():
        environment.setdefault(name, value)
    return environment
