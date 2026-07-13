import io
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.updates import UpdateChecker, UpdateCheckError


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def opener_for(data):
    payload = json.dumps(data).encode("utf-8")
    return lambda _request, timeout: Response(payload)


def manifest(version="1.2.0"):
    return {
        "schema_version": 1,
        "version": version,
        "release_url": "https://example.com/releases/1.2.0",
        "msi_url": "https://example.com/app.msi",
        "msi_sha256": "a" * 64,
        "notes": "Melhorias",
    }


def test_reports_newer_semantic_version():
    result = UpdateChecker("https://example.com/manifest.json", opener_for(manifest())).check("1.1.9")
    assert result.available
    assert result.latest_version == "1.2.0"


def test_rejects_insecure_urls_and_invalid_checksum():
    with pytest.raises(UpdateCheckError):
        UpdateChecker("http://example.com/manifest.json")
    invalid = manifest()
    invalid["msi_sha256"] = "bad"
    with pytest.raises(UpdateCheckError):
        UpdateChecker("https://example.com/manifest.json", opener_for(invalid)).check("1.0.0")
