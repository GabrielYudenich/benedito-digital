"""Local, media-aware project history for Benedito Digital."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Union

try:
    from .migrations import (
        CURRENT_WORKSPACE_SCHEMA,
        FutureWorkspaceVersion,
        WorkspaceMigrationError,
        migrate_workspace,
    )
    from .recovery import JsonRecoveryError, atomic_write_json, load_json_with_recovery
except ImportError:
    from migrations import (
        CURRENT_WORKSPACE_SCHEMA,
        FutureWorkspaceVersion,
        WorkspaceMigrationError,
        migrate_workspace,
    )
    from recovery import JsonRecoveryError, atomic_write_json, load_json_with_recovery


PathLike = Union[str, os.PathLike]
ProgressCallback = Callable[[float], None]


class WorkspaceError(Exception):
    """Base error raised by the project workspace."""


class InvalidBranchName(WorkspaceError):
    """Raised when a branch name is unsafe or unsupported."""


class WorkspaceCancelled(WorkspaceError):
    """Raised when a long-running workspace operation is cancelled."""


class ProjectWorkspace:
    """Stores local branches, operations and deduplicated binary artifacts."""

    SCHEMA_VERSION = CURRENT_WORKSPACE_SCHEMA
    DEFAULT_BRANCH = "principal"
    BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

    def __init__(self, project_path: PathLike):
        self.project_path = Path(project_path).resolve()
        self.metadata_dir = self.project_path / "metadata"
        self.workspace_file = self.metadata_dir / "workspace.json"
        self.operations_dir = self.project_path / "history" / "operations"
        self.objects_dir = self.project_path / "objects" / "sha256"
        self.media_dir = self.project_path / "media"
        self.originals_dir = self.media_dir / "originals"
        self.proxies_dir = self.media_dir / "proxies"
        self.frames_dir = self.project_path / "frames" / "originals"
        self.worktrees_dir = self.project_path / "worktrees"
        self.cache_dir = self.project_path / "cache"
        self.exports_dir = self.project_path / "exports"
        self.recovery_report = {
            "recovered": False,
            "source": None,
            "quarantined": None,
            "migrations": [],
        }
        self.data = self._load_or_initialize()

    @classmethod
    def initialize(cls, project_path: PathLike) -> "ProjectWorkspace":
        """Create or load the workspace attached to a project directory."""
        return cls(project_path)

    def _load_or_initialize(self) -> Dict[str, Any]:
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.operations_dir.mkdir(parents=True, exist_ok=True)
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        self.proxies_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "jobs").mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "thumbnails").mkdir(parents=True, exist_ok=True)
        (self.exports_dir / "previews").mkdir(parents=True, exist_ok=True)
        (self.exports_dir / "renders").mkdir(parents=True, exist_ok=True)

        recovery_files_exist = (
            self.workspace_file.exists()
            or self.workspace_file.with_name(f"{self.workspace_file.name}.bak").exists()
            or any(self.metadata_dir.glob(f".{self.workspace_file.name}.*.tmp"))
        )
        if recovery_files_exist:
            try:
                loaded = load_json_with_recovery(
                    self.workspace_file,
                    validator=self._validate_workspace_candidate,
                    fatal_exceptions=(FutureWorkspaceVersion,),
                )
                data, migrations = migrate_workspace(loaded.data, self._now())
            except (JsonRecoveryError, WorkspaceMigrationError) as error:
                raise WorkspaceError(str(error)) from error
            self._validate_workspace(data)
            data.setdefault("proxies", {})
            self.recovery_report = {
                "recovered": loaded.recovered,
                "source": loaded.source,
                "quarantined": str(loaded.quarantined) if loaded.quarantined else None,
                "migrations": migrations,
            }
            if migrations:
                self._write_workspace(data)
            return data

        now = self._now()
        data = {
            "schema_version": self.SCHEMA_VERSION,
            "format": "benedito-workspace",
            "schema_migrations": [],
            "active_branch": self.DEFAULT_BRANCH,
            "branches": {
                self.DEFAULT_BRANCH: {
                    "head": None,
                    "created_at": now,
                    "source_branch": None,
                    "frame_statuses": {},
                }
            },
            "originals": {},
            "proxies": {},
            "created_at": now,
            "updated_at": now,
        }
        self._write_workspace(data)
        return data

    @property
    def active_branch(self) -> str:
        return self.data["active_branch"]

    def list_branches(self) -> List[Dict[str, Any]]:
        """Return branch metadata, marking the active branch."""
        return [
            {"name": name, "active": name == self.active_branch, **metadata}
            for name, metadata in sorted(self.data["branches"].items())
        ]

    def create_branch(self, name: str, source_branch: Optional[str] = None) -> Dict[str, Any]:
        """Create a lightweight branch from an existing branch head."""
        self._validate_branch_name(name)
        if name in self.data["branches"]:
            raise WorkspaceError(f"Branch already exists: {name}")

        source = source_branch or self.active_branch
        source_data = self._get_branch(source)
        branch_data = {
            "head": source_data["head"],
            "created_at": self._now(),
            "source_branch": source,
            "frame_statuses": dict(source_data.get("frame_statuses", {})),
        }
        self.data["branches"][name] = branch_data
        self._save()
        return {"name": name, **branch_data}

    def checkout(self, name: str) -> None:
        """Select the branch that receives new operations."""
        self._get_branch(name)
        self.data["active_branch"] = name
        self._save()

    def commit_operation(
        self,
        operation_type: str,
        payload: Optional[Mapping[str, Any]] = None,
        frame_number: Optional[int] = None,
        artifacts: Optional[Mapping[str, PathLike]] = None,
    ) -> Dict[str, Any]:
        """Commit an editable operation and any exact binary artifacts."""
        if not operation_type or not operation_type.strip():
            raise WorkspaceError("Operation type cannot be empty")
        if frame_number is not None and frame_number < 0:
            raise WorkspaceError("Frame number cannot be negative")

        branch_name = self.active_branch
        branch = self._get_branch(branch_name)
        stored_artifacts = {
            label: self.store_object(path)
            for label, path in (artifacts or {}).items()
        }
        operation_id = uuid.uuid4().hex
        operation = {
            "id": operation_id,
            "parent": branch["head"],
            "branch": branch_name,
            "type": operation_type.strip(),
            "frame_number": frame_number,
            "payload": dict(payload or {}),
            "artifacts": stored_artifacts,
            "created_at": self._now(),
        }
        self._atomic_write_json(self.operations_dir / f"{operation_id}.json", operation)
        branch["head"] = operation_id
        self._save()
        return operation

    def reset_frame(self, frame_number: int) -> Dict[str, Any]:
        """Record a non-destructive reset to the immutable original frame."""
        return self.commit_operation(
            "frame.reset",
            payload={"target": "original"},
            frame_number=frame_number,
        )

    def get_history(self, branch_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return operations from oldest to newest for a branch."""
        branch = self._get_branch(branch_name or self.active_branch)
        history = []
        operation_id = branch["head"]
        visited = set()

        while operation_id:
            if operation_id in visited:
                raise WorkspaceError("Cycle detected in operation history")
            visited.add(operation_id)
            operation_path = self.operations_dir / f"{operation_id}.json"
            if not operation_path.exists():
                raise WorkspaceError(f"Missing operation: {operation_id}")
            operation = self._read_json(operation_path)
            history.append(operation)
            operation_id = operation.get("parent")

        history.reverse()
        return history

    def get_frame_history(
        self, frame_number: int, branch_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return operations that directly target a frame."""
        return [
            operation
            for operation in self.get_history(branch_name)
            if operation.get("frame_number") == frame_number
        ]

    def set_frame_status(
        self, frame_number: int, status: str, note: str = ""
    ) -> Dict[str, Any]:
        """Set a branch-local review status and record it in history."""
        allowed = {
            "unmarked",
            "review",
            "dust",
            "scratch",
            "stain",
            "missing",
            "perforation",
            "approved",
        }
        if status not in allowed:
            raise WorkspaceError(f"Invalid frame status: {status}")
        operation = self.commit_operation(
            "frame.status",
            payload={"status": status, "note": note.strip()},
            frame_number=frame_number,
        )
        branch = self._get_branch(self.active_branch)
        statuses = branch.setdefault("frame_statuses", {})
        if status == "unmarked":
            statuses.pop(str(frame_number), None)
        else:
            statuses[str(frame_number)] = {
                "status": status,
                "note": note.strip(),
                "updated_at": operation["created_at"],
            }
        self._save()
        return operation

    def get_frame_status(
        self, frame_number: int, branch_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        branch = self._get_branch(branch_name or self.active_branch)
        return branch.get("frame_statuses", {}).get(str(frame_number))

    def get_frame_statuses(
        self, branch_name: Optional[str] = None
    ) -> Dict[int, Dict[str, Any]]:
        branch = self._get_branch(branch_name or self.active_branch)
        return {
            int(frame_number): dict(value)
            for frame_number, value in branch.get("frame_statuses", {}).items()
        }

    def compare_branches(self, target_branch: str, source_branch: str) -> Dict[str, Any]:
        """Describe divergent operations and frame-level conflicts between branches."""
        if target_branch == source_branch:
            raise WorkspaceError("Cannot compare a branch with itself")
        target_history = self.get_history(target_branch)
        source_history = self.get_history(source_branch)
        target_ids = {operation["id"] for operation in target_history}
        common_ancestor = next(
            (operation["id"] for operation in reversed(source_history) if operation["id"] in target_ids),
            None,
        )

        def divergent(history):
            if common_ancestor is None:
                return list(history)
            ancestor_index = next(
                index for index, operation in enumerate(history) if operation["id"] == common_ancestor
            )
            return history[ancestor_index + 1 :]

        target_divergent = divergent(target_history)
        source_divergent = divergent(source_history)
        incorporated_source_ids = {
            operation.get("payload", {}).get("source_operation")
            for operation in target_history
            if operation.get("type") == "merge.replay"
            and operation.get("payload", {}).get("source_branch") == source_branch
        }
        source_divergent = [
            operation for operation in source_divergent
            if operation["id"] not in incorporated_source_ids
        ]
        target_frames = self._operations_by_frame(target_divergent)
        source_frames = self._operations_by_frame(source_divergent)
        conflict_frames = sorted(set(target_frames) & set(source_frames))
        return {
            "target_branch": target_branch,
            "source_branch": source_branch,
            "common_ancestor": common_ancestor,
            "target_operations": target_divergent,
            "source_operations": source_divergent,
            "conflicts": [
                {
                    "frame_number": frame_number,
                    "target_operations": target_frames[frame_number],
                    "source_operations": source_frames[frame_number],
                    "target_summary": self._operation_summary(target_frames[frame_number]),
                    "source_summary": self._operation_summary(source_frames[frame_number]),
                }
                for frame_number in conflict_frames
            ],
            "source_only_frames": sorted(set(source_frames) - set(target_frames)),
            "target_only_frames": sorted(set(target_frames) - set(source_frames)),
        }

    def merge_branch(
        self,
        source_branch: str,
        resolutions: Optional[Mapping[int, str]] = None,
        target_branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Merge a branch by replaying exact references and resolving each conflicting frame."""
        target = target_branch or self.active_branch
        comparison = self.compare_branches(target, source_branch)
        choices = {int(frame): choice for frame, choice in (resolutions or {}).items()}
        conflicts = {item["frame_number"] for item in comparison["conflicts"]}
        invalid = {frame: choices.get(frame) for frame in conflicts if choices.get(frame) not in {"target", "source"}}
        if invalid:
            raise WorkspaceError("Every conflicting frame requires target or source resolution")

        previous_branch = self.active_branch
        self.checkout(target)
        replayed = 0
        try:
            for operation in comparison["source_operations"]:
                frame_number = operation.get("frame_number")
                if frame_number in conflicts and choices[frame_number] == "target":
                    continue
                self._commit_referenced_operation(
                    "merge.replay",
                    frame_number=frame_number,
                    payload={
                        "source_branch": source_branch,
                        "source_operation": operation["id"],
                        "source_type": operation.get("type"),
                        "source_payload": operation.get("payload", {}),
                    },
                    artifacts=operation.get("artifacts", {}),
                )
                replayed += 1

            target_statuses = self._get_branch(target).setdefault("frame_statuses", {})
            source_statuses = self._get_branch(source_branch).get("frame_statuses", {})
            for frame_number, status in source_statuses.items():
                numeric_frame = int(frame_number)
                if numeric_frame not in conflicts or choices.get(numeric_frame) == "source":
                    target_statuses[frame_number] = dict(status)
            merge_operation = self.commit_operation(
                "branch.merge",
                payload={
                    "source_branch": source_branch,
                    "common_ancestor": comparison["common_ancestor"],
                    "resolutions": {str(frame): choices[frame] for frame in sorted(conflicts)},
                    "replayed_operations": replayed,
                },
            )
            self._save()
        finally:
            if previous_branch != target:
                self.checkout(previous_branch)
        return {
            "operation": merge_operation,
            "replayed_operations": replayed,
            "conflicts": len(conflicts),
            "target_branch": target,
            "source_branch": source_branch,
        }

    @staticmethod
    def _operations_by_frame(operations: Iterable[Mapping[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for operation in operations:
            frame_number = operation.get("frame_number")
            if frame_number is not None:
                grouped.setdefault(int(frame_number), []).append(dict(operation))
        return grouped

    @staticmethod
    def _operation_summary(operations: Iterable[Mapping[str, Any]]) -> str:
        types = [str(operation.get("type", "operação")) for operation in operations]
        return ", ".join(types[-3:]) + (f" (+{len(types) - 3})" if len(types) > 3 else "")

    def _commit_referenced_operation(
        self,
        operation_type: str,
        frame_number: Optional[int],
        payload: Mapping[str, Any],
        artifacts: Mapping[str, Mapping[str, Any]],
    ) -> Dict[str, Any]:
        for artifact in artifacts.values():
            digest = str(artifact.get("sha256", ""))
            if not self.object_path(digest).is_file():
                raise WorkspaceError(f"Missing object required by merge: {digest}")
        branch_name = self.active_branch
        branch = self._get_branch(branch_name)
        operation_id = uuid.uuid4().hex
        operation = {
            "id": operation_id,
            "parent": branch["head"],
            "branch": branch_name,
            "type": operation_type,
            "frame_number": frame_number,
            "payload": dict(payload),
            "artifacts": {label: dict(artifact) for label, artifact in artifacts.items()},
            "created_at": self._now(),
        }
        self._atomic_write_json(self.operations_dir / f"{operation_id}.json", operation)
        branch["head"] = operation_id
        self._save()
        return operation

    def export_branch(
        self,
        package_path: PathLike,
        branch_name: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """Export branch history and referenced objects without source media."""
        name = branch_name or self.active_branch
        branch = self._get_branch(name)
        history = self.get_history(name)
        object_hashes = sorted(
            {
                artifact["sha256"]
                for operation in history
                for artifact in operation.get("artifacts", {}).values()
            }
        )
        manifest = {
            "format": "benedito-branch-package",
            "version": 1,
            "branch": name,
            "head": branch.get("head"),
            "frame_statuses": branch.get("frame_statuses", {}),
            "originals": [
                {"sha256": digest, "size": record["size"]}
                for digest, record in sorted(self.data.get("originals", {}).items())
            ],
            "operations": [operation["id"] for operation in history],
            "objects": object_hashes,
            "exported_at": self._now(),
        }
        destination = Path(package_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        total_entries = max(1, len(history) + len(object_hashes) + 1)
        completed = 0
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as package:
                package.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                )
                completed += 1
                for operation in history:
                    if cancel_callback and cancel_callback():
                        raise WorkspaceCancelled("Branch export cancelled")
                    package.write(
                        self.operations_dir / f"{operation['id']}.json",
                        f"operations/{operation['id']}.json",
                    )
                    completed += 1
                    if progress_callback:
                        progress_callback(completed * 100.0 / total_entries)
                for digest in object_hashes:
                    if cancel_callback and cancel_callback():
                        raise WorkspaceCancelled("Branch export cancelled")
                    package.write(self.object_path(digest), f"objects/{digest}")
                    completed += 1
                    if progress_callback:
                        progress_callback(completed * 100.0 / total_entries)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        if progress_callback:
            progress_callback(100.0)
        return manifest

    def import_branch(
        self,
        package_path: PathLike,
        branch_name: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> str:
        """Import and verify a local branch package against registered originals."""
        source = Path(package_path)
        if not source.is_file():
            raise WorkspaceError(f"Branch package does not exist: {source}")
        with zipfile.ZipFile(source, "r") as package:
            try:
                manifest = json.loads(package.read("manifest.json"))
            except (KeyError, json.JSONDecodeError) as error:
                raise WorkspaceError("Invalid branch package manifest") from error
            if manifest.get("format") != "benedito-branch-package" or manifest.get("version") != 1:
                raise WorkspaceError("Unsupported branch package")
            local_originals = self.data.get("originals", {})
            missing_originals = [
                item["sha256"]
                for item in manifest.get("originals", [])
                if item.get("sha256") not in local_originals
            ]
            if missing_originals:
                raise WorkspaceError(
                    "The package belongs to different or unregistered source media"
                )

            name = branch_name or manifest.get("branch") or "importado"
            if name in self.data["branches"]:
                name = f"{name[:47]}-importado-{uuid.uuid4().hex[:8]}"
            self._validate_branch_name(name)
            operations = manifest.get("operations", [])
            objects = manifest.get("objects", [])
            if (
                not isinstance(operations, list)
                or any(not isinstance(value, str) for value in operations)
                or len(operations) != len(set(operations))
            ):
                raise WorkspaceError("Invalid or duplicate operation list in package")
            if (
                not isinstance(objects, list)
                or any(not isinstance(value, str) for value in objects)
                or len(objects) != len(set(objects))
            ):
                raise WorkspaceError("Invalid or duplicate object list in package")
            if any(not re.fullmatch(r"[0-9a-f]{64}", str(digest)) for digest in objects):
                raise WorkspaceError("Invalid object identifier in package")
            packaged_operations = []
            previous_operation = None
            referenced_objects = set()
            for operation_id in operations:
                if not re.fullmatch(r"[0-9a-f]{32}", str(operation_id)):
                    raise WorkspaceError("Invalid operation identifier in package")
                try:
                    operation = json.loads(package.read(f"operations/{operation_id}.json"))
                except (KeyError, json.JSONDecodeError) as error:
                    raise WorkspaceError("Missing or invalid operation in package") from error
                if operation.get("id") != operation_id or operation.get("parent") != previous_operation:
                    raise WorkspaceError("Operation history chain is invalid")
                frame_number = operation.get("frame_number")
                if frame_number is not None and (not isinstance(frame_number, int) or frame_number < 0):
                    raise WorkspaceError("Invalid frame number in operation")
                for artifact in operation.get("artifacts", {}).values():
                    digest = artifact.get("sha256")
                    if digest not in objects:
                        raise WorkspaceError("Operation references an undeclared object")
                    referenced_objects.add(digest)
                packaged_operations.append(operation)
                previous_operation = operation_id
            if manifest.get("head") != previous_operation:
                raise WorkspaceError("Package head does not match operation history")
            if referenced_objects != set(objects):
                raise WorkspaceError("Package contains missing or unreferenced objects")
            total_entries = max(1, len(operations) + len(objects))
            completed = 0

            for operation_id, operation in zip(operations, packaged_operations):
                if cancel_callback and cancel_callback():
                    raise WorkspaceCancelled("Branch import cancelled")
                self._atomic_write_json(
                    self.operations_dir / f"{operation_id}.json", operation
                )
                completed += 1
                if progress_callback:
                    progress_callback(completed * 100.0 / total_entries)

            for digest in objects:
                if cancel_callback and cancel_callback():
                    raise WorkspaceCancelled("Branch import cancelled")
                destination = self.object_path(digest)
                if not destination.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    temporary = destination.with_name(
                        f".{destination.name}.{uuid.uuid4().hex}.tmp"
                    )
                    hasher = hashlib.sha256()
                    try:
                        with package.open(f"objects/{digest}") as input_file, temporary.open("wb") as output_file:
                            while True:
                                chunk = input_file.read(8 * 1024 * 1024)
                                if not chunk:
                                    break
                                hasher.update(chunk)
                                output_file.write(chunk)
                        if hasher.hexdigest() != digest:
                            raise WorkspaceError("Imported object checksum mismatch")
                        os.replace(temporary, destination)
                    finally:
                        if temporary.exists():
                            temporary.unlink()
                completed += 1
                if progress_callback:
                    progress_callback(completed * 100.0 / total_entries)

        self.data["branches"][name] = {
            "head": manifest.get("head"),
            "created_at": self._now(),
            "source_branch": f"package:{manifest.get('branch', 'unknown')}",
            "frame_statuses": manifest.get("frame_statuses", {}),
        }
        self._save()
        if progress_callback:
            progress_callback(100.0)
        return name

    def latest_frame_artifact(
        self,
        frame_number: int,
        label: str,
        branch_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the newest artifact for a frame, respecting reset operations."""
        for operation in reversed(self.get_frame_history(frame_number, branch_name)):
            if operation.get("type") == "frame.reset":
                return None
            if label in operation.get("payload", {}).get("cleared_artifacts", []):
                return None
            artifact = operation.get("artifacts", {}).get(label)
            if artifact:
                return artifact
        return None

    def resolve_frame_source(
        self, frame_number: int, branch_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Resolve the effective edited frame, falling back to its immutable original."""
        if frame_number < 0:
            raise WorkspaceError("Frame number cannot be negative")
        artifact = self.latest_frame_artifact(frame_number, "frame", branch_name)
        if artifact:
            path = self.object_path(str(artifact.get("sha256", "")))
            if path.is_file():
                return {"path": path, "kind": "edited", "artifact": artifact}
        originals = sorted(
            path
            for path in self.frames_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
        )
        if frame_number < len(originals):
            return {"path": originals[frame_number], "kind": "original", "artifact": None}
        return None

    def materialize_object(self, artifact: Mapping[str, Any], destination: PathLike) -> Path:
        """Materialize a stored artifact atomically into a branch worktree."""
        digest = str(artifact.get("sha256", ""))
        source = self.object_path(digest)
        if not source.is_file():
            raise WorkspaceError(f"Missing object: {digest}")
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination_path.with_name(
            f".{destination_path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination_path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return destination_path

    def branch_worktree(self, branch_name: Optional[str] = None) -> Path:
        """Return an isolated materialized worktree for a non-principal branch."""
        name = branch_name or self.active_branch
        self._get_branch(name)
        path = self.worktrees_dir / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def store_object(self, source_path: PathLike) -> Dict[str, Any]:
        """Store a file once, addressed by its SHA-256 digest."""
        source = Path(source_path)
        if not source.is_file():
            raise WorkspaceError(f"Artifact does not exist: {source}")

        digest = self.hash_file(source)
        destination = self.object_path(digest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination)

        return {
            "sha256": digest,
            "size": source.stat().st_size,
            "name": source.name,
        }

    def object_path(self, digest: str) -> Path:
        """Return the local path for a content-addressed object."""
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise WorkspaceError("Invalid SHA-256 digest")
        return self.objects_dir / digest[:2] / digest[2:]

    def register_original(
        self,
        source_path: PathLike,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """Register an immutable source without duplicating it in the object store."""
        source = Path(source_path).resolve()
        if not source.is_file():
            raise WorkspaceError(f"Original does not exist: {source}")

        digest = self.hash_file(source, progress_callback)
        record = {
            "sha256": digest,
            "size": source.stat().st_size,
            "path": self._portable_path(source),
            "registered_at": self._now(),
        }
        self.data["originals"][digest] = record
        self._save()
        return record

    def import_original(
        self,
        source_path: PathLike,
        destination_name: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
        chunk_size: int = 8 * 1024 * 1024,
    ) -> Dict[str, Any]:
        """Copy and hash an original in one streaming, transactional pass."""
        source = Path(source_path).resolve()
        if not source.is_file():
            raise WorkspaceError(f"Original does not exist: {source}")

        safe_name = Path(destination_name or source.name).name
        if not safe_name or safe_name in {".", ".."}:
            raise WorkspaceError("Invalid original file name")
        destination_dir = self.originals_dir
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / safe_name
        if destination.exists() and destination.resolve() != source:
            raise WorkspaceError(f"Original already exists: {safe_name}")
        if destination.resolve() == source:
            return self.register_original(source, progress_callback)

        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        digest = hashlib.sha256()
        total_size = source.stat().st_size
        processed = 0
        try:
            with source.open("rb") as input_file, temporary.open("xb") as output_file:
                while True:
                    if cancel_callback and cancel_callback():
                        raise WorkspaceCancelled("Original import cancelled")
                    chunk = input_file.read(chunk_size)
                    if not chunk:
                        break
                    output_file.write(chunk)
                    digest.update(chunk)
                    processed += len(chunk)
                    if progress_callback:
                        progress_callback(100.0 if total_size == 0 else processed * 100.0 / total_size)
                output_file.flush()
                os.fsync(output_file.fileno())
            if cancel_callback and cancel_callback():
                raise WorkspaceCancelled("Original import cancelled")
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()

        if progress_callback and total_size == 0:
            progress_callback(100.0)
        checksum = digest.hexdigest()
        record = {
            "sha256": checksum,
            "size": total_size,
            "path": self._portable_path(destination),
            "registered_at": self._now(),
        }
        self.data["originals"][checksum] = record
        self._save()
        return record

    def verify_original(
        self,
        digest: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> bool:
        """Verify that a registered source still matches its immutable identity."""
        record = self.data["originals"].get(digest)
        if not record:
            raise WorkspaceError(f"Unknown original: {digest}")
        path = self._resolve_portable_path(record["path"])
        if not path.is_file() or path.stat().st_size != record["size"]:
            return False
        return self.hash_file(path, progress_callback) == digest

    def register_proxy(
        self, video_name: str, proxy_path: PathLike, width: int
    ) -> Dict[str, Any]:
        """Register a recreatable local editing proxy."""
        path = Path(proxy_path).resolve()
        if not path.is_file():
            raise WorkspaceError(f"Proxy does not exist: {path}")
        record = {
            "path": self._portable_path(path),
            "width": int(width),
            "size": path.stat().st_size,
            "created_at": self._now(),
        }
        self.data.setdefault("proxies", {})[video_name] = record
        self._save()
        return record

    def get_proxy_path(self, video_name: str) -> Optional[Path]:
        record = self.data.get("proxies", {}).get(video_name)
        if not record:
            return None
        path = self._resolve_portable_path(record["path"])
        return path if path.is_file() else None

    @staticmethod
    def hash_file(
        path: PathLike,
        progress_callback: Optional[ProgressCallback] = None,
        chunk_size: int = 8 * 1024 * 1024,
    ) -> str:
        """Hash a file incrementally without loading it into memory."""
        source = Path(path)
        total_size = source.stat().st_size
        processed = 0
        digest = hashlib.sha256()

        with source.open("rb") as file_handle:
            while True:
                chunk = file_handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
                processed += len(chunk)
                if progress_callback:
                    progress_callback(100.0 if total_size == 0 else processed * 100.0 / total_size)

        if progress_callback and total_size == 0:
            progress_callback(100.0)
        return digest.hexdigest()

    def _save(self) -> None:
        self.data["updated_at"] = self._now()
        self._write_workspace(self.data)

    def _write_workspace(self, data: Dict[str, Any]) -> None:
        self._atomic_write_json(self.workspace_file, data)

    def _get_branch(self, name: str) -> Dict[str, Any]:
        branch = self.data["branches"].get(name)
        if branch is None:
            raise WorkspaceError(f"Unknown branch: {name}")
        return branch

    def _validate_workspace(self, data: Dict[str, Any]) -> None:
        if data.get("schema_version") != self.SCHEMA_VERSION:
            raise WorkspaceError("Unsupported workspace schema version")
        if data.get("format") != "benedito-workspace":
            raise WorkspaceError("Invalid workspace format")
        branches = data.get("branches")
        active_branch = data.get("active_branch")
        if not isinstance(branches, dict) or active_branch not in branches:
            raise WorkspaceError("Invalid workspace branch data")
        if not isinstance(data.get("originals"), dict):
            raise WorkspaceError("Invalid workspace originals data")

    def _validate_workspace_candidate(self, data: Dict[str, Any]) -> None:
        migrated, _applied = migrate_workspace(data, self._now())
        self._validate_workspace(migrated)

    @classmethod
    def _validate_branch_name(cls, name: str) -> None:
        if not cls.BRANCH_PATTERN.fullmatch(name or ""):
            raise InvalidBranchName(
                "Use 1-64 letters, numbers, dots, underscores or hyphens"
            )

    def _portable_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.project_path).as_posix()
        except ValueError:
            return str(path)

    def _resolve_portable_path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.project_path / path

    @staticmethod
    def _read_json(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)

    @staticmethod
    def _atomic_write_json(path: Path, data: Mapping[str, Any]) -> None:
        atomic_write_json(path, data)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
