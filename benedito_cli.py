#!/usr/bin/env python3
"""Command-line collaboration workflows for Benedito Digital."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.collaboration import CollaborationError, FolderCollaborationRemote
from lib.modules.project.workspace import ProjectWorkspace, WorkspaceError


def parser():
    command = argparse.ArgumentParser(prog="benedito", description="Colaboração local do Benedito Digital")
    subcommands = command.add_subparsers(dest="command", required=True)
    initialize = subcommands.add_parser("remote-init", help="Preparar uma pasta compartilhada")
    initialize.add_argument("remote")
    initialize.add_argument("--label", default="Equipe Benedito")
    for name in ("status", "push", "pull"):
        action = subcommands.add_parser(name)
        action.add_argument("project", help="Pasta do projeto Benedito")
        action.add_argument("remote", help="Pasta local, NAS ou sincronizada")
        if name in {"push", "pull"}:
            action.add_argument("--branch")
        if name == "pull":
            action.add_argument("--as", dest="local_branch")
    return command


def progress(value):
    print(f"\r{value:6.2f}%", end="", file=sys.stderr, flush=True)
    if value >= 100:
        print(file=sys.stderr)


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        remote = FolderCollaborationRemote(arguments.remote)
        if arguments.command == "remote-init":
            result = remote.initialize(arguments.label)
        else:
            workspace = ProjectWorkspace(arguments.project)
            if arguments.command == "status":
                result = {"branches": remote.list_branches(workspace)}
            elif arguments.command == "push":
                result = asdict(remote.push(workspace, arguments.branch, progress_callback=progress))
            else:
                branch = arguments.branch
                if not branch:
                    branches = remote.list_branches(workspace)
                    if not branches:
                        raise CollaborationError("Remote has no branches for this project")
                    branch = branches[0]["name"]
                result = asdict(
                    remote.pull(
                        workspace,
                        branch,
                        local_branch_name=arguments.local_branch,
                        progress_callback=progress,
                    )
                )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (CollaborationError, WorkspaceError, OSError) as error:
        print(f"erro: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
