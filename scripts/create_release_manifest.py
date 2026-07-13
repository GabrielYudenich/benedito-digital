"""Create a reproducible public release manifest from an MSI."""

import argparse
import hashlib
import json
from pathlib import Path


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--msi", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--repository", default="GabrielYudenich/benedito-digital")
    parser.add_argument("--output", type=Path, default=Path("release-manifest.json"))
    parser.add_argument("--notes", default="Nova versão do Benedito Digital.")
    args = parser.parse_args()
    filename = args.msi.name
    base = f"https://github.com/{args.repository}/releases"
    data = {
        "schema_version": 1,
        "version": args.version,
        "release_url": f"{base}/tag/v{args.version}",
        "msi_url": f"{base}/download/v{args.version}/{filename}",
        "msi_sha256": hash_file(args.msi),
        "notes": args.notes,
    }
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
