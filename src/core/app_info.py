"""Authoritative application metadata loaded from the bundled configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from core.paths import resource_path


@dataclass(frozen=True)
class AppInfo:
    name: str
    version: str
    author: str
    language: str
    license: str
    description: str


@lru_cache(maxsize=1)
def get_app_info() -> AppInfo:
    data = json.loads(resource_path("config.json").read_text(encoding="utf-8"))
    required = {"software", "version", "author", "language", "license", "description"}
    if not isinstance(data, dict) or not required.issubset(data):
        raise RuntimeError("config.json does not contain valid application metadata")
    return AppInfo(
        name=str(data["software"]),
        version=str(data["version"]),
        author=str(data["author"]),
        language=str(data["language"]),
        license=str(data["license"]),
        description=str(data["description"]),
    )
