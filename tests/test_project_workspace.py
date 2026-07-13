import hashlib
import json
import os
import sys
import zipfile

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from lib.modules.project.workspace import (
    InvalidBranchName,
    ProjectWorkspace,
    WorkspaceCancelled,
    WorkspaceError,
)


def test_initializes_legacy_project_without_changing_project_metadata(tmp_path):
    project_path = tmp_path / "legacy"
    metadata_dir = project_path / "metadata"
    metadata_dir.mkdir(parents=True)
    project_file = metadata_dir / "project.json"
    project_file.write_text('{"name": "legacy"}', encoding="utf-8")

    workspace = ProjectWorkspace.initialize(project_path)

    assert workspace.active_branch == "principal"
    assert workspace.list_branches()[0]["head"] is None
    assert project_file.read_text(encoding="utf-8") == '{"name": "legacy"}'


def test_workspace_creates_separated_project_layout(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")

    assert workspace.originals_dir.is_dir()
    assert workspace.proxies_dir.is_dir()
    assert workspace.frames_dir.is_dir()
    assert workspace.branch_worktree().is_dir()
    assert (workspace.cache_dir / "jobs").is_dir()
    assert (workspace.cache_dir / "thumbnails").is_dir()
    assert (workspace.exports_dir / "previews").is_dir()
    assert (workspace.exports_dir / "renders").is_dir()


def test_workspace_schema_one_is_migrated_without_losing_history(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    operation = workspace.commit_operation("frame.note", frame_number=7)
    legacy = json.loads(workspace.workspace_file.read_text(encoding="utf-8"))
    legacy["schema_version"] = 1
    legacy.pop("format")
    legacy.pop("schema_migrations")
    workspace.workspace_file.write_text(json.dumps(legacy), encoding="utf-8")

    migrated = ProjectWorkspace.initialize(workspace.project_path)

    assert migrated.data["schema_version"] == 2
    assert migrated.data["format"] == "benedito-workspace"
    assert migrated.recovery_report["migrations"] == [2]
    assert migrated.get_history()[0]["id"] == operation["id"]


def test_corrupt_workspace_recovers_previous_atomic_backup(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    workspace.create_branch("tratamento")
    workspace.workspace_file.write_text("{interrompido", encoding="utf-8")

    recovered = ProjectWorkspace.initialize(workspace.project_path)

    assert recovered.recovery_report["recovered"] is True
    assert recovered.recovery_report["source"] == "backup"
    assert [branch["name"] for branch in recovered.list_branches()] == ["principal"]
    assert recovered.workspace_file.with_name("workspace.json.bak").is_file()
    assert recovered.recovery_report["quarantined"]
    assert os.path.isfile(recovered.recovery_report["quarantined"])


def test_interrupted_workspace_save_recovers_complete_temporary_copy(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    pending = json.loads(workspace.workspace_file.read_text(encoding="utf-8"))
    pending["branches"]["resgate"] = {
        "head": None,
        "created_at": pending["created_at"],
        "source_branch": "principal",
        "frame_statuses": {},
    }
    temporary = workspace.workspace_file.with_name(".workspace.json.resgate.tmp")
    temporary.write_text(json.dumps(pending), encoding="utf-8")
    workspace.workspace_file.write_text("", encoding="utf-8")

    recovered = ProjectWorkspace.initialize(workspace.project_path)

    assert recovered.recovery_report["source"] == "temporary"
    assert {branch["name"] for branch in recovered.list_branches()} == {
        "principal",
        "resgate",
    }
    assert not temporary.exists()


def test_future_workspace_schema_is_not_silently_downgraded(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    workspace.create_branch("backup-existente")
    future = json.loads(workspace.workspace_file.read_text(encoding="utf-8"))
    future["schema_version"] = 999
    workspace.workspace_file.write_text(json.dumps(future), encoding="utf-8")

    with pytest.raises(WorkspaceError, match="suporta até"):
        ProjectWorkspace.initialize(workspace.project_path)

    assert json.loads(workspace.workspace_file.read_text(encoding="utf-8"))["schema_version"] == 999


def test_branches_share_history_then_diverge(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    first = workspace.commit_operation(
        "frame.transform",
        frame_number=42,
        payload={"translate_x": -12.5, "translate_y": 8.0},
    )
    workspace.create_branch("rolo-1")
    workspace.checkout("rolo-1")
    branch_operation = workspace.commit_operation(
        "brush.stroke",
        frame_number=42,
        payload={"radius": 18, "points": [[10, 20], [12, 22]]},
    )

    assert [item["id"] for item in workspace.get_history("principal")] == [first["id"]]
    assert [item["id"] for item in workspace.get_history("rolo-1")] == [
        first["id"],
        branch_operation["id"],
    ]


def test_frame_review_statuses_are_branch_local_and_inherited(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    workspace.set_frame_status(10, "scratch", "Risco vertical")
    workspace.create_branch("tratamento")
    workspace.checkout("tratamento")

    assert workspace.get_frame_status(10)["status"] == "scratch"
    workspace.set_frame_status(10, "approved")

    assert workspace.get_frame_status(10, "tratamento")["status"] == "approved"
    assert workspace.get_frame_status(10, "principal")["status"] == "scratch"


def test_unmarked_removes_frame_review_status(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    workspace.set_frame_status(4, "review")

    workspace.set_frame_status(4, "unmarked")

    assert workspace.get_frame_status(4) is None


def test_branch_package_transfers_only_history_and_objects(tmp_path):
    source_workspace = ProjectWorkspace.initialize(tmp_path / "source-project")
    original = source_workspace.originals_dir / "scan.mov"
    original.write_bytes(b"same source media")
    original_record = source_workspace.register_original(original)
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"exact edited pixels")
    source_workspace.commit_operation(
        "brush.stroke", frame_number=5, artifacts={"mask": mask}
    )
    package = tmp_path / "rolo.bdpack"

    manifest = source_workspace.export_branch(package)

    target_workspace = ProjectWorkspace.initialize(tmp_path / "target-project")
    target_original = target_workspace.originals_dir / "scan.mov"
    target_original.write_bytes(b"same source media")
    target_workspace.register_original(target_original)
    imported_name = target_workspace.import_branch(package)

    assert manifest["originals"] == [
        {"sha256": original_record["sha256"], "size": len(b"same source media")}
    ]
    assert imported_name.startswith("principal-importado-")
    assert len(target_workspace.get_history(imported_name)) == 1
    with zipfile.ZipFile(package) as archive:
        assert not any("scan.mov" in name for name in archive.namelist())


def test_branch_package_rejects_different_original(tmp_path):
    source_workspace = ProjectWorkspace.initialize(tmp_path / "source")
    original = source_workspace.originals_dir / "scan.mov"
    original.write_bytes(b"source A")
    source_workspace.register_original(original)
    package = tmp_path / "branch.bdpack"
    source_workspace.export_branch(package)

    target_workspace = ProjectWorkspace.initialize(tmp_path / "target")
    target_original = target_workspace.originals_dir / "scan.mov"
    target_original.write_bytes(b"source B")
    target_workspace.register_original(target_original)

    with pytest.raises(WorkspaceError, match="different or unregistered"):
        target_workspace.import_branch(package)


def test_artifacts_are_deduplicated_and_referenced_by_hash(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    first_tile = tmp_path / "tile-a.bin"
    second_tile = tmp_path / "tile-b.bin"
    first_tile.write_bytes(b"same exact pixels")
    second_tile.write_bytes(b"same exact pixels")

    first = workspace.commit_operation(
        "frame.patch", frame_number=7, artifacts={"tile": first_tile}
    )
    second = workspace.commit_operation(
        "frame.patch", frame_number=8, artifacts={"tile": second_tile}
    )

    first_object = first["artifacts"]["tile"]
    second_object = second["artifacts"]["tile"]
    assert first_object["sha256"] == second_object["sha256"]
    assert workspace.object_path(first_object["sha256"]).read_bytes() == b"same exact pixels"
    assert len(list(workspace.objects_dir.rglob("*"))) == 2


def test_branch_inherits_and_materializes_latest_frame_artifact(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"exact mask pixels")
    workspace.commit_operation(
        "brush.stroke", frame_number=12, artifacts={"mask": mask}
    )
    workspace.create_branch("rolo-2")
    workspace.checkout("rolo-2")

    artifact = workspace.latest_frame_artifact(12, "mask")
    destination = workspace.branch_worktree() / "masks" / "mask_frame_000012.png"
    workspace.materialize_object(artifact, destination)

    assert destination.read_bytes() == b"exact mask pixels"
    assert workspace.branch_worktree().name == "rolo-2"


def test_frame_reset_hides_inherited_artifact(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"mask")
    workspace.commit_operation(
        "brush.stroke", frame_number=3, artifacts={"mask": mask}
    )

    workspace.reset_frame(3)

    assert workspace.latest_frame_artifact(3, "mask") is None


def test_history_operation_can_clear_one_artifact_without_hiding_others(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    frame = tmp_path / "frame.png"
    mask = tmp_path / "mask.png"
    frame.write_bytes(b"edited frame")
    mask.write_bytes(b"mask")
    workspace.commit_operation(
        "frame.patch", frame_number=3, artifacts={"frame": frame, "mask": mask}
    )
    workspace.commit_operation(
        "history.undo",
        frame_number=3,
        payload={"cleared_artifacts": ["frame"]},
        artifacts={"mask": mask},
    )

    assert workspace.latest_frame_artifact(3, "frame") is None
    assert workspace.latest_frame_artifact(3, "mask") is not None


def test_resolve_frame_source_prefers_branch_artifact_then_original(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    original = workspace.frames_dir / "frame_000001.png"
    original.write_bytes(b"original")

    initial = workspace.resolve_frame_source(0)
    edited = tmp_path / "edited.png"
    edited.write_bytes(b"edited")
    operation = workspace.commit_operation(
        "clone.stroke", frame_number=0, artifacts={"frame": edited}
    )
    resolved = workspace.resolve_frame_source(0)

    assert initial == {"path": original, "kind": "original", "artifact": None}
    assert resolved["kind"] == "edited"
    assert resolved["artifact"]["sha256"] == operation["artifacts"]["frame"]["sha256"]


def test_original_is_registered_and_verified_without_copying(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    original = workspace.originals_dir / "scan.mov"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"immutable source")
    progress = []

    record = workspace.register_original(original, progress.append)

    assert record["sha256"] == hashlib.sha256(b"immutable source").hexdigest()
    assert record["path"] == "media/originals/scan.mov"
    assert workspace.verify_original(record["sha256"])
    assert progress[-1] == 100.0
    original.write_bytes(b"changed source")
    assert not workspace.verify_original(record["sha256"])


def test_original_hashing_can_be_cancelled_between_chunks(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    original = tmp_path / "large.mov"
    original.write_bytes(b"a" * 64)
    checks = iter((False, True))

    with pytest.raises(WorkspaceCancelled, match="verification cancelled"):
        workspace.hash_file(
            original,
            chunk_size=32,
            cancel_callback=lambda: next(checks, True),
        )

def test_original_import_copies_and_hashes_in_one_pass(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    source = tmp_path / "outside.mov"
    source.write_bytes(b"video-data" * 100)
    progress = []

    record = workspace.import_original(source, progress_callback=progress.append, chunk_size=17)
    imported = workspace.project_path / record["path"]

    assert imported.read_bytes() == source.read_bytes()
    assert record["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert progress[-1] == 100.0


def test_proxy_registration_is_local_and_recreatable(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    proxy = workspace.proxies_dir / "scan_proxy.mp4"
    proxy.write_bytes(b"lightweight proxy")

    record = workspace.register_proxy("scan.mov", proxy, 1280)

    assert record["width"] == 1280
    assert workspace.get_proxy_path("scan.mov") == proxy
    proxy.unlink()
    assert workspace.get_proxy_path("scan.mov") is None


def test_cancelled_original_import_leaves_no_partial_file(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    source = tmp_path / "large.mov"
    source.write_bytes(b"x" * 100)
    progress = []

    with pytest.raises(WorkspaceCancelled):
        workspace.import_original(
            source,
            progress_callback=progress.append,
            cancel_callback=lambda: bool(progress),
            chunk_size=10,
        )

    destination_dir = workspace.originals_dir
    assert not (destination_dir / source.name).exists()
    assert list(destination_dir.iterdir()) == []


def test_reset_frame_is_an_operation_not_a_destructive_delete(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")

    reset = workspace.reset_frame(15)

    assert reset["type"] == "frame.reset"
    assert reset["payload"] == {"target": "original"}
    assert workspace.get_frame_history(15) == [reset]


@pytest.mark.parametrize("name", ["../escape", "rolo 1", "", "a" * 65])
def test_rejects_unsafe_branch_names(tmp_path, name):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")

    with pytest.raises(InvalidBranchName):
        workspace.create_branch(name)


def test_rejects_unknown_branch(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")

    with pytest.raises(WorkspaceError):
        workspace.checkout("inexistente")


def test_compare_branches_reports_only_divergent_frame_conflicts(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    workspace.commit_operation("frame.note", frame_number=1)
    workspace.create_branch("colega")
    workspace.commit_operation("brush.stroke", frame_number=10)
    workspace.checkout("colega")
    workspace.commit_operation("clone.stroke", frame_number=10)
    workspace.commit_operation("frame.transform", frame_number=11)

    comparison = workspace.compare_branches("principal", "colega")

    assert comparison["common_ancestor"] is not None
    assert [item["frame_number"] for item in comparison["conflicts"]] == [10]
    assert comparison["source_only_frames"] == [11]
    assert comparison["target_only_frames"] == []


def test_merge_requires_an_explicit_choice_for_each_conflicting_frame(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    workspace.create_branch("colega")
    workspace.commit_operation("brush.stroke", frame_number=7)
    workspace.checkout("colega")
    workspace.commit_operation("brush.stroke", frame_number=7)

    with pytest.raises(WorkspaceError, match="Every conflicting frame"):
        workspace.merge_branch("principal", target_branch="colega")


def test_merge_source_replays_exact_artifact_without_duplicating_object(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    workspace.create_branch("colega")
    target_image = tmp_path / "target.png"
    target_image.write_bytes(b"target pixels")
    source_operation = workspace.commit_operation(
        "frame.patch", frame_number=4, artifacts={"frame": target_image}
    )
    workspace.checkout("colega")
    source_image = tmp_path / "source.png"
    source_image.write_bytes(b"source pixels")
    workspace.commit_operation(
        "frame.patch", frame_number=4, artifacts={"frame": source_image}
    )
    object_count = len([path for path in workspace.objects_dir.rglob("*") if path.is_file()])

    result = workspace.merge_branch(
        "principal", target_branch="colega", resolutions={4: "source"}
    )

    artifact = workspace.latest_frame_artifact(4, "frame", "colega")
    assert artifact["sha256"] == source_operation["artifacts"]["frame"]["sha256"]
    assert result["conflicts"] == 1
    assert len([path for path in workspace.objects_dir.rglob("*") if path.is_file()]) == object_count


def test_merge_target_keeps_local_frame_and_auto_replays_source_only_frame(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    workspace.create_branch("colega")
    source_frame = tmp_path / "source.png"
    source_frame.write_bytes(b"source")
    workspace.commit_operation(
        "frame.patch", frame_number=2, artifacts={"frame": source_frame}
    )
    workspace.commit_operation("frame.transform", frame_number=3, payload={"x": 12})
    workspace.checkout("colega")
    target_frame = tmp_path / "target.png"
    target_frame.write_bytes(b"target")
    target_operation = workspace.commit_operation(
        "frame.patch", frame_number=2, artifacts={"frame": target_frame}
    )

    result = workspace.merge_branch(
        "principal", target_branch="colega", resolutions={2: "target"}
    )

    assert workspace.latest_frame_artifact(2, "frame", "colega")["sha256"] == target_operation["artifacts"]["frame"]["sha256"]
    assert any(operation["type"] == "merge.replay" for operation in workspace.get_frame_history(3, "colega"))
    assert result["replayed_operations"] == 1


def test_repeated_merge_does_not_replay_the_same_source_operations(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    workspace.create_branch("colega")
    workspace.checkout("colega")
    workspace.commit_operation("frame.transform", frame_number=8, payload={"x": 2})
    workspace.checkout("principal")

    first = workspace.merge_branch("colega")
    second = workspace.merge_branch("colega")

    assert first["replayed_operations"] == 1
    assert second["replayed_operations"] == 0


def test_import_rejects_a_broken_operation_chain_before_creating_branch(tmp_path):
    workspace = ProjectWorkspace.initialize(tmp_path / "project")
    operation_id = "a" * 32
    manifest = {
        "format": "benedito-branch-package",
        "version": 1,
        "branch": "malformada",
        "head": operation_id,
        "frame_statuses": {},
        "originals": [],
        "operations": [operation_id],
        "objects": [],
    }
    operation = {
        "id": operation_id,
        "parent": "b" * 32,
        "branch": "malformada",
        "type": "frame.note",
        "frame_number": 1,
        "payload": {},
        "artifacts": {},
    }
    package = tmp_path / "invalid.bdpack"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(f"operations/{operation_id}.json", json.dumps(operation))

    with pytest.raises(WorkspaceError, match="history chain"):
        workspace.import_branch(package)

    assert [branch["name"] for branch in workspace.list_branches()] == ["principal"]
