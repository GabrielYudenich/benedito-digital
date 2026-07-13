#!/usr/bin/env python3
"""Reject oversized or legacy vendored files from the current Git tree."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


FORBIDDEN_PREFIXES = (
    "legacy/",
    "src/models/",
    "models/Restormer-main/",
    "models/SwinIR-main/",
    "models/pytorch-unet-dust-master/",
)


def tracked_files(repository: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def audit_repository(repository: Path, maximum_bytes: int) -> list[str]:
    problems = []
    for relative_path in tracked_files(repository):
        normalized = relative_path.replace("\\", "/")
        if normalized.startswith(FORBIDDEN_PREFIXES):
            problems.append(f"caminho legado rastreado: {normalized}")
            continue
        path = repository / relative_path
        if path.is_file() and path.stat().st_size > maximum_bytes:
            size_mib = path.stat().st_size / (1024 * 1024)
            problems.append(f"arquivo rastreado com {size_mib:.1f} MiB: {normalized}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maximum-mib", type=int, default=20)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    problems = audit_repository(repository, args.maximum_mib * 1024 * 1024)
    if problems:
        print("Falha na higiene do repositório:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print(f"Higiene do repositório válida: nenhum arquivo rastreado acima de {args.maximum_mib} MiB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
