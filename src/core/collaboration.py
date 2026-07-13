"""Incremental collaboration through a trusted shared folder, without sockets."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import uuid
import zipfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional


class CollaborationError(Exception):
    """Raised when a shared-folder remote is invalid or inconsistent."""


@dataclass(frozen=True)
class SyncResult:
    action: str
    project_id: str
    branch: str
    head: Optional[str]
    operations: int
    objects: int
    transferred_bytes: int
    local_branch: Optional[str] = None


class FolderCollaborationRemote:
    """Content-addressed remote stored in a local, NAS, or synchronized folder."""

    SCHEMA_VERSION = 1
    SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

    def __init__(self, folder):
        selected = Path(folder).expanduser().resolve()
        self.root = selected / ".benedito-remote"
        self.index_file = self.root / "index.json"
        self.operations_dir = self.root / "operations"
        self.objects_dir = self.root / "objects" / "sha256"
        self.snapshots_dir = self.root / "snapshots"
        self.lock_file = self.root / ".write.lock"

    def initialize(self, label: str = "Equipe Benedito") -> Dict:
        self.operations_dir.mkdir(parents=True, exist_ok=True)
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_file.exists():
            self._atomic_json(
                self.index_file,
                {
                    "schema_version": self.SCHEMA_VERSION,
                    "remote_id": uuid.uuid4().hex,
                    "label": label.strip() or "Equipe Benedito",
                    "projects": {},
                },
            )
        return self._read_index()

    def push(
        self,
        workspace,
        branch_name: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> SyncResult:
        self.initialize()
        project = self._project_identity(workspace)
        branch = branch_name or workspace.active_branch
        self._validate_name(branch, "branch")
        history = workspace.get_history(branch)
        head = history[-1]["id"] if history else None
        object_hashes = sorted(
            {
                artifact["sha256"]
                for operation in history
                for artifact in operation.get("artifacts", {}).values()
            }
        )
        transferred_bytes = 0
        uploaded_operations = 0
        uploaded_objects = 0
        total_items = max(1, len(history) + len(object_hashes))
        completed_items = 0
        with self._write_lock():
            index = self._read_index()
            for operation in history:
                if cancel_callback and cancel_callback():
                    raise CollaborationError("Push cancelled")
                source = workspace.operations_dir / f"{operation['id']}.json"
                destination = self.operations_dir / f"{operation['id']}.json"
                if not destination.exists():
                    transferred_bytes += self._copy_atomic(source, destination)
                    uploaded_operations += 1
                completed_items += 1
                if progress_callback:
                    progress_callback(completed_items * 90.0 / total_items)
            for digest in object_hashes:
                if cancel_callback and cancel_callback():
                    raise CollaborationError("Push cancelled")
                source = workspace.object_path(digest)
                destination = self._remote_object_path(digest)
                if not destination.exists():
                    if workspace.hash_file(source) != digest:
                        raise CollaborationError("Local object checksum mismatch")
                    transferred_bytes += self._copy_atomic(source, destination)
                    uploaded_objects += 1
                completed_items += 1
                if progress_callback:
                    progress_callback(completed_items * 90.0 / total_items)

            snapshot = {
                "format": "benedito-remote-snapshot",
                "version": self.SCHEMA_VERSION,
                "project_id": project["id"],
                "project_name": project["name"],
                "branch": branch,
                "head": head,
                "frame_statuses": workspace._get_branch(branch).get("frame_statuses", {}),
                "originals": [
                    {"sha256": digest, "size": record["size"]}
                    for digest, record in sorted(workspace.data.get("originals", {}).items())
                ],
                "operations": [operation["id"] for operation in history],
                "objects": object_hashes,
                "published_at": workspace._now(),
            }
            snapshot_path = self._snapshot_path(project["id"], branch, head)
            self._atomic_json(snapshot_path, snapshot)
            projects = index.setdefault("projects", {})
            project_entry = projects.setdefault(
                project["id"], {"name": project["name"], "branches": {}}
            )
            project_entry["name"] = project["name"]
            project_entry.setdefault("branches", {})[branch] = {
                "head": head,
                "snapshot": str(snapshot_path.relative_to(self.root)).replace("\\", "/"),
                "published_at": snapshot["published_at"],
                "operations": len(history),
                "objects": len(object_hashes),
            }
            self._atomic_json(self.index_file, index)
        if progress_callback:
            progress_callback(100.0)
        return SyncResult(
            action="push",
            project_id=project["id"],
            branch=branch,
            head=head,
            operations=uploaded_operations,
            objects=uploaded_objects,
            transferred_bytes=transferred_bytes,
        )

    def pull(
        self,
        workspace,
        branch_name: str,
        local_branch_name: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> SyncResult:
        project = self._project_identity(workspace)
        snapshot = self._load_branch_snapshot(project["id"], branch_name)
        cache = workspace.cache_dir / "jobs"
        cache.mkdir(parents=True, exist_ok=True)
        package_path = cache / f"pull-{uuid.uuid4().hex}.bdpack"
        transferred_bytes = 0
        missing_objects = 0
        total_items = max(
            1, len(snapshot.get("operations", [])) + len(snapshot.get("objects", []))
        )
        completed_items = 0
        try:
            manifest = {
                "format": "benedito-branch-package",
                "version": 1,
                "branch": snapshot["branch"],
                "head": snapshot.get("head"),
                "frame_statuses": snapshot.get("frame_statuses", {}),
                "originals": snapshot.get("originals", []),
                "operations": snapshot.get("operations", []),
                "objects": snapshot.get("objects", []),
                "exported_at": snapshot.get("published_at"),
            }
            with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_STORED) as package:
                package.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                for operation_id in manifest["operations"]:
                    if cancel_callback and cancel_callback():
                        raise CollaborationError("Pull cancelled")
                    self._validate_operation_id(operation_id)
                    source = self.operations_dir / f"{operation_id}.json"
                    if not source.is_file():
                        raise CollaborationError("Remote operation is missing")
                    package.write(source, f"operations/{operation_id}.json")
                    transferred_bytes += source.stat().st_size
                    completed_items += 1
                    if progress_callback:
                        progress_callback(completed_items * 70.0 / total_items)
                for digest in manifest["objects"]:
                    if cancel_callback and cancel_callback():
                        raise CollaborationError("Pull cancelled")
                    self._validate_digest(digest)
                    if workspace.object_path(digest).exists():
                        completed_items += 1
                        if progress_callback:
                            progress_callback(completed_items * 70.0 / total_items)
                        continue
                    source = self._remote_object_path(digest)
                    if not source.is_file() or self._hash_file(source) != digest:
                        raise CollaborationError("Remote object is missing or corrupted")
                    package.write(source, f"objects/{digest}")
                    transferred_bytes += source.stat().st_size
                    missing_objects += 1
                    completed_items += 1
                    if progress_callback:
                        progress_callback(completed_items * 70.0 / total_items)
            imported = workspace.import_branch(
                package_path,
                branch_name=local_branch_name,
                progress_callback=(
                    (lambda value: progress_callback(70.0 + value * 0.3))
                    if progress_callback
                    else None
                ),
                cancel_callback=cancel_callback,
            )
        finally:
            package_path.unlink(missing_ok=True)
        if progress_callback:
            progress_callback(100.0)
        return SyncResult(
            action="pull",
            project_id=project["id"],
            branch=branch_name,
            head=snapshot.get("head"),
            operations=len(snapshot.get("operations", [])),
            objects=missing_objects,
            transferred_bytes=transferred_bytes,
            local_branch=imported,
        )

    def list_branches(self, workspace) -> List[Dict]:
        project = self._project_identity(workspace)
        index = self._read_index()
        branches = (
            index.get("projects", {})
            .get(project["id"], {})
            .get("branches", {})
        )
        result = []
        for name, data in branches.items():
            if not self.SAFE_NAME.fullmatch(name) or not isinstance(data, dict):
                continue
            result.append({"name": name, **data})
        return sorted(result, key=lambda item: item.get("published_at", ""), reverse=True)

    def _load_branch_snapshot(self, project_id: str, branch_name: str) -> Dict:
        self._validate_name(branch_name, "branch")
        index = self._read_index()
        try:
            relative = index["projects"][project_id]["branches"][branch_name]["snapshot"]
        except (KeyError, TypeError) as error:
            raise CollaborationError("Remote branch was not found") from error
        snapshot_path = (self.root / relative).resolve()
        if self.root not in snapshot_path.parents:
            raise CollaborationError("Remote snapshot path escapes its repository")
        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CollaborationError("Remote snapshot is invalid") from error
        if (
            snapshot.get("format") != "benedito-remote-snapshot"
            or snapshot.get("version") != self.SCHEMA_VERSION
            or snapshot.get("project_id") != project_id
            or snapshot.get("branch") != branch_name
        ):
            raise CollaborationError("Remote snapshot identity mismatch")
        return snapshot

    def _snapshot_path(self, project_id: str, branch: str, head: Optional[str]) -> Path:
        self._validate_name(project_id, "project")
        self._validate_name(branch, "branch")
        filename = f"{head or 'empty'}.json"
        return self.snapshots_dir / project_id / branch / filename

    def _remote_object_path(self, digest: str) -> Path:
        self._validate_digest(digest)
        return self.objects_dir / digest[:2] / digest

    @staticmethod
    def _project_identity(workspace) -> Dict[str, str]:
        metadata_file = workspace.metadata_dir / "project.json"
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CollaborationError("Project metadata is unavailable") from error
        project_id = str(metadata.get("id", ""))
        project_name = str(metadata.get("name", ""))
        FolderCollaborationRemote._validate_name(project_id, "project")
        if not project_name:
            raise CollaborationError("Project name is unavailable")
        return {"id": project_id, "name": project_name}

    def _read_index(self) -> Dict:
        try:
            data = json.loads(self.index_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CollaborationError("Shared folder is not a valid Benedito remote") from error
        if data.get("schema_version") != self.SCHEMA_VERSION:
            raise CollaborationError("Unsupported remote schema")
        return data

    @contextmanager
    def _write_lock(self, timeout: float = 15.0):
        deadline = time.monotonic() + timeout
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor = None
        while descriptor is None:
            try:
                descriptor = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
            except FileExistsError:
                try:
                    if time.time() - self.lock_file.stat().st_mtime > 300:
                        self.lock_file.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise CollaborationError("Remote is busy with another writer")
                time.sleep(0.1)
        try:
            yield
        finally:
            if descriptor is not None:
                os.close(descriptor)
            self.lock_file.unlink(missing_ok=True)

    @staticmethod
    def _copy_atomic(source: Path, destination: Path) -> int:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination.stat().st_size

    @staticmethod
    def _atomic_json(path: Path, data: Dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def _validate_name(cls, value: str, kind: str) -> None:
        if not cls.SAFE_NAME.fullmatch(str(value)):
            raise CollaborationError(f"Invalid {kind} identifier")

    @staticmethod
    def _validate_digest(value: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", str(value)):
            raise CollaborationError("Invalid object digest")

    @staticmethod
    def _validate_operation_id(value: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", str(value)):
            raise CollaborationError("Invalid operation identifier")

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file_handle:
            for chunk in iter(lambda: file_handle.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
