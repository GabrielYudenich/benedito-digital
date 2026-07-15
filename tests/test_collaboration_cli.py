import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lib.modules.project.workspace import ProjectWorkspace


def make_project(path):
    ProjectWorkspace(path)
    (path / "metadata" / "project.json").write_text(
        json.dumps({"id": "cli-project", "name": "CLI"}), encoding="utf-8"
    )


def run_cli(*arguments):
    return subprocess.run(
        [sys.executable, str(ROOT / "benedito_cli.py"), *map(str, arguments)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_initializes_pushes_and_lists_remote(tmp_path):
    project = tmp_path / "project"
    remote = tmp_path / "remote"
    make_project(project)

    assert run_cli("remote-init", remote).returncode == 0
    pushed = run_cli("push", project, remote)
    status = run_cli("status", project, remote)

    assert pushed.returncode == 0
    assert status.returncode == 0
    assert json.loads(status.stdout)["branches"][0]["name"] == "principal"
