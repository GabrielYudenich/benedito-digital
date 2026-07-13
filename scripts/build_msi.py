"""Build a per-user Windows MSI from a PyInstaller onedir distribution."""

from __future__ import annotations

import argparse
import os
import re
import sys
import uuid
import warnings
from pathlib import Path


PRODUCT_NAME = "Benedito Digital"
MANUFACTURER = "Projeto Benedito Digital"
UPGRADE_CODE = "{B03D65D8-8E74-4F28-9149-4EBBF61A8437}"
IDENTIFIER_NAMESPACE = uuid.UUID("c1d54ea1-674d-4eb5-8793-1981c5731dcb")


def normalize_msi_version(version: str) -> str:
    parts = version.strip().split(".")
    if not 1 <= len(parts) <= 3 or any(not part.isdigit() for part in parts):
        raise ValueError("MSI version must contain one to three numeric parts")
    values = [int(part) for part in parts] + [0] * (3 - len(parts))
    if values[0] > 255 or values[1] > 255 or values[2] > 65535:
        raise ValueError("MSI version is outside Windows Installer limits")
    return ".".join(str(value) for value in values)


def deterministic_guid(kind: str, value: str) -> str:
    return "{" + str(uuid.uuid5(IDENTIFIER_NAMESPACE, f"{kind}:{value}")).upper() + "}"


def build_msi(source_dir: Path, output_path: Path, version: str) -> Path:
    if os.name != "nt" or sys.version_info[:2] >= (3, 13):
        raise RuntimeError("Native MSI builds require Windows and Python 3.11 or 3.12")
    source_dir = source_dir.resolve()
    output_path = output_path.resolve()
    executable = source_dir / f"{PRODUCT_NAME}.exe"
    if not source_dir.is_dir() or not executable.is_file():
        raise FileNotFoundError(f"Invalid PyInstaller distribution: {source_dir}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)
    version = normalize_msi_version(version)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import msilib
        from msilib import CAB, Directory, Feature, add_data, add_tables, schema, sequence

    product_code = deterministic_guid("product", version)
    database = msilib.init_database(
        str(output_path), schema, PRODUCT_NAME, product_code, version, MANUFACTURER
    )
    add_tables(database, sequence)
    add_data(
        database,
        "Property",
        [
            ("UpgradeCode", UPGRADE_CODE),
            ("INSTALLLEVEL", "1"),
            ("ARPNOMODIFY", "1"),
            ("ARPURLINFOABOUT", "https://github.com/GabrielYudenich/benedito-digital"),
            ("ARPHELPLINK", "https://github.com/GabrielYudenich/benedito-digital/issues"),
            ("SecureCustomProperties", "OLDERVERSIONBEINGUPGRADED"),
        ],
    )

    cabinet = CAB("benedito_files")
    root = Directory(database, cabinet, None, str(source_dir), "TARGETDIR", "SourceDir")
    local_app_data = Directory(database, cabinet, root, ".", "LocalAppDataFolder", ".")
    install_dir = Directory(
        database,
        cabinet,
        local_app_data,
        ".",
        "INSTALLDIR",
        "BENEDI~1|Benedito Digital",
    )
    feature = Feature(
        database,
        "MainFeature",
        PRODUCT_NAME,
        "Aplicativo de restauração audiovisual",
        1,
        1,
        directory="INSTALLDIR",
    )
    feature.set_current()
    executable_key = _add_directory_tree(
        database, cabinet, install_dir, source_dir, feature, Directory
    )

    programs = Directory(database, cabinet, root, ".", "ProgramMenuFolder", ".")
    menu_dir = Directory(
        database,
        cabinet,
        programs,
        ".",
        "ApplicationProgramsFolder",
        "BENEDI~1|Benedito Digital",
    )
    component_id = "ApplicationShortcut"
    registry_id = "BeneditoDigitalInstalled"
    add_data(
        database,
        "Component",
        [
            (
                component_id,
                deterministic_guid("component", "start-menu"),
                menu_dir.logical,
                4,
                None,
                registry_id,
            )
        ],
    )
    add_data(database, "FeatureComponents", [(feature.id, component_id)])
    add_data(
        database,
        "Registry",
        [(registry_id, 1, r"Software\Benedito Digital", "Installed", "#1", component_id)],
    )
    add_data(
        database,
        "Shortcut",
        [
            (
                "ApplicationStartMenuShortcut",
                menu_dir.logical,
                "BENEDI~1|Benedito Digital",
                component_id,
                f"[#{executable_key}]",
                None,
                "Restauração audiovisual local",
                None,
                None,
                None,
                1,
                install_dir.logical,
            )
        ],
    )
    add_data(
        database,
        "Upgrade",
        [(UPGRADE_CODE, None, version, None, 257, None, "OLDERVERSIONBEINGUPGRADED")],
    )
    cabinet.commit(database)
    database.Commit()
    return output_path


def _add_directory_tree(
    database, cabinet, root_directory, source_dir, feature, directory_type
):
    executable_key = None
    queue = [(root_directory, source_dir, Path("."))]
    while queue:
        logical_directory, physical_directory, relative_directory = queue.pop(0)
        paths = sorted(physical_directory.iterdir(), key=lambda item: item.name.lower())
        files = [path for path in paths if path.is_file()]
        if files:
            component_name = _identifier("Files", relative_directory.as_posix())
            logical_directory.start_component(
                component_name,
                feature,
                0,
                uuid=deterministic_guid("component", relative_directory.as_posix()),
            )
        for path in paths:
            if path.is_dir():
                child_relative = relative_directory / path.name
                child = directory_type(
                    database,
                    cabinet,
                    logical_directory,
                    path.name,
                    _identifier("Dir", child_relative.as_posix()),
                    f"{logical_directory.make_short(path.name)}|{path.name}",
                )
                queue.append((child, path, child_relative))
            elif path.is_file():
                key = logical_directory.add_file(path.name)
                if path.name == f"{PRODUCT_NAME}.exe" and relative_directory == Path("."):
                    executable_key = key
        database.Commit()
    if not executable_key:
        raise RuntimeError("Main executable was not added to MSI")
    return executable_key


def _identifier(prefix: str, value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.]", "_", value)
    digest = uuid.uuid5(IDENTIFIER_NAMESPACE, value).hex[:10]
    return f"{prefix}_{sanitized[-45:]}_{digest}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()
    result = build_msi(args.source, args.output, args.version)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
