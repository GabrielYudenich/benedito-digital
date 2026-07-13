"""Safe update availability checks using a small HTTPS JSON manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class UpdateCheckError(Exception):
    pass


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    available: bool
    release_url: str
    msi_url: str
    msi_sha256: str
    notes: str


class UpdateChecker:
    MAX_MANIFEST_SIZE = 256 * 1024

    def __init__(self, manifest_url, opener=urlopen):
        self.manifest_url = str(manifest_url)
        self.opener = opener
        self._require_https(self.manifest_url)

    def check(self, current_version, timeout=8.0):
        request = Request(
            self.manifest_url,
            headers={"User-Agent": f"Benedito-Digital/{current_version}"},
        )
        try:
            with self.opener(request, timeout=timeout) as response:
                payload = response.read(self.MAX_MANIFEST_SIZE + 1)
        except Exception as error:
            raise UpdateCheckError(f"Não foi possível consultar atualizações: {error}") from error
        if len(payload) > self.MAX_MANIFEST_SIZE:
            raise UpdateCheckError("Manifesto de atualização é grande demais")
        try:
            manifest = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise UpdateCheckError("Manifesto de atualização inválido") from error
        if manifest.get("schema_version") != 1:
            raise UpdateCheckError("Versão de manifesto não suportada")
        latest = str(manifest.get("version", ""))
        self._version_tuple(latest)
        release_url = str(manifest.get("release_url", ""))
        msi_url = str(manifest.get("msi_url", ""))
        self._require_https(release_url)
        self._require_https(msi_url)
        checksum = str(manifest.get("msi_sha256", "")).lower()
        if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
            raise UpdateCheckError("Checksum MSI inválido no manifesto")
        return UpdateInfo(
            current_version=str(current_version),
            latest_version=latest,
            available=self._version_tuple(latest) > self._version_tuple(str(current_version)),
            release_url=release_url,
            msi_url=msi_url,
            msi_sha256=checksum,
            notes=str(manifest.get("notes", "")),
        )

    @staticmethod
    def _version_tuple(value):
        parts = str(value).split(".")
        if not 1 <= len(parts) <= 4 or any(not part.isdigit() for part in parts):
            raise UpdateCheckError("Versão de atualização inválida")
        return tuple(int(part) for part in parts) + (0,) * (4 - len(parts))

    @staticmethod
    def _require_https(value):
        parsed = urlparse(str(value))
        if parsed.scheme != "https" or not parsed.netloc:
            raise UpdateCheckError("Atualizações exigem endereço HTTPS")
