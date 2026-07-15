"""Versioned migrations for Benedito Digital project metadata."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Tuple


CURRENT_WORKSPACE_SCHEMA = 2


class WorkspaceMigrationError(Exception):
    """Raised when a workspace cannot be migrated safely."""


class FutureWorkspaceVersion(WorkspaceMigrationError):
    """Raised when a newer Benedito Digital version is required."""


def migrate_workspace(
    source: Dict[str, Any], migrated_at: str
) -> Tuple[Dict[str, Any], List[int]]:
    data = deepcopy(source)
    version = data.get("schema_version")
    if not isinstance(version, int) or version < 1:
        raise WorkspaceMigrationError("Versão de workspace ausente ou inválida")
    if version > CURRENT_WORKSPACE_SCHEMA:
        raise FutureWorkspaceVersion(
            f"Workspace usa schema {version}; esta versão suporta até {CURRENT_WORKSPACE_SCHEMA}"
        )

    applied = []
    while version < CURRENT_WORKSPACE_SCHEMA:
        if version == 1:
            data.setdefault("format", "benedito-workspace")
            data.setdefault("schema_migrations", []).append(
                {"from": 1, "to": 2, "migrated_at": migrated_at}
            )
            version = 2
            data["schema_version"] = version
            applied.append(version)
            continue
        raise WorkspaceMigrationError(f"Não existe migração para o schema {version}")

    data.setdefault("format", "benedito-workspace")
    data.setdefault("schema_migrations", [])
    return data, applied
