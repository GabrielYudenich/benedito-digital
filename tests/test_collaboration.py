import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.collaboration import CollaborationError, FolderCollaborationRemote
from lib.modules.project.workspace import ProjectWorkspace


def workspace_with_identity(path, project_id="project-123"):
    workspace = ProjectWorkspace.initialize(path)
    metadata = {"id": project_id, "name": "Rolo compartilhado"}
    (path / "metadata" / "project.json").write_text(json.dumps(metadata), encoding="utf-8")
    return workspace


def register_same_original(source, target, tmp_path):
    original = tmp_path / "source.mov"
    original.write_bytes(b"original-film")
    source.import_original(original)
    target.import_original(original)


def test_push_and_incremental_pull_transfer_branch_without_original(tmp_path):
    source = workspace_with_identity(tmp_path / "source")
    target = workspace_with_identity(tmp_path / "target")
    register_same_original(source, target, tmp_path)
    edited = tmp_path / "edited.png"
    edited.write_bytes(b"restored-frame")
    source.commit_operation("brush.stroke", frame_number=4, artifacts={"result": edited})
    remote = FolderCollaborationRemote(tmp_path / "shared")

    pushed = remote.push(source)
    pulled = remote.pull(target, "principal")

    assert pushed.objects == 1
    assert pushed.transferred_bytes > 0
    assert pulled.objects == 1
    assert pulled.local_branch.startswith("principal")
    assert target.get_frame_history(4, pulled.local_branch)
    assert not any((tmp_path / "shared").rglob("source.mov"))


def test_repeated_push_uploads_only_missing_content(tmp_path):
    workspace = workspace_with_identity(tmp_path / "project")
    edited = tmp_path / "edited.png"
    edited.write_bytes(b"same-object")
    workspace.commit_operation("filter.local", frame_number=1, artifacts={"result": edited})
    remote = FolderCollaborationRemote(tmp_path / "shared")

    first = remote.push(workspace)
    second = remote.push(workspace)

    assert first.operations == 1
    assert first.objects == 1
    assert second.operations == 0
    assert second.objects == 0
    assert second.transferred_bytes == 0


def test_pull_rejects_project_with_different_identity(tmp_path):
    source = workspace_with_identity(tmp_path / "source", "project-a")
    target = workspace_with_identity(tmp_path / "target", "project-b")
    remote = FolderCollaborationRemote(tmp_path / "shared")
    remote.push(source)

    try:
        remote.pull(target, "principal")
    except CollaborationError as error:
        assert "not found" in str(error).lower()
    else:
        raise AssertionError("Different project identity was accepted")


def test_snapshot_path_cannot_escape_remote(tmp_path):
    workspace = workspace_with_identity(tmp_path / "project")
    remote = FolderCollaborationRemote(tmp_path / "shared")
    remote.push(workspace)
    index = json.loads(remote.index_file.read_text(encoding="utf-8"))
    index["projects"]["project-123"]["branches"]["principal"]["snapshot"] = "../../escape.json"
    remote.index_file.write_text(json.dumps(index), encoding="utf-8")

    try:
        remote.pull(workspace, "principal")
    except CollaborationError as error:
        assert "escapes" in str(error).lower()
    else:
        raise AssertionError("Escaping snapshot path was accepted")
