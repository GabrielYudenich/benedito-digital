"""Per-user configurable keyboard shortcuts."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ShortcutDefinition:
    action: str
    label: str
    default: str


SHORTCUT_DEFINITIONS = (
    ShortcutDefinition("previous_frame", "Frame anterior", "Left"),
    ShortcutDefinition("next_frame", "Próximo frame", "Right"),
    ShortcutDefinition("first_frame", "Primeiro frame", "Up"),
    ShortcutDefinition("last_frame", "Último frame", "Down"),
    ShortcutDefinition("range_start", "Início do trecho", "I"),
    ShortcutDefinition("range_end", "Final do trecho", "O"),
    ShortcutDefinition("undo", "Desfazer", "Ctrl+Z"),
    ShortcutDefinition("redo", "Refazer", "Ctrl+Y"),
    ShortcutDefinition("signal_frame", "Sinalizar frame", "Shift+S"),
    ShortcutDefinition("toggle_play", "Reproduzir ou pausar referência", "Space"),
    ShortcutDefinition("media_catalog", "Abrir catálogo de mídia", "F5"),
    ShortcutDefinition("frame_catalog", "Abrir catálogo de frames", "F6"),
    ShortcutDefinition("second_screen", "Abrir segunda tela", "F8"),
    ShortcutDefinition("compare", "Comparar original e resultado", "C"),
    ShortcutDefinition("properties", "Abrir propriedades avançadas", "Ctrl+,"),
    ShortcutDefinition("shortcut_settings", "Configurar atalhos", "Ctrl+Alt+K"),
    ShortcutDefinition("positions", "Posicionamentos de câmera", "Ctrl+Alt+C"),
    ShortcutDefinition("clean_plate", "Criar placa limpa", "Ctrl+Alt+P"),
    ShortcutDefinition("stabilize", "Estabilizar trecho ativo", "Ctrl+Alt+S"),
    ShortcutDefinition("preview", "Pré-renderizar trecho ativo", "Ctrl+Alt+V"),
    ShortcutDefinition("render", "Renderizar resultado final", "Ctrl+Alt+R"),
    ShortcutDefinition("timeline", "Timeline multipista", "Ctrl+Shift+T"),
    ShortcutDefinition("collaboration", "Colaboração da equipe", "Ctrl+Shift+C"),
    ShortcutDefinition("scopes", "Scopes de cor", "Ctrl+Shift+S"),
    ShortcutDefinition("useful_start", "Definir início útil", "Ctrl+["),
    ShortcutDefinition("useful_end", "Definir final útil", "Ctrl+]"),
    ShortcutDefinition("help", "Ajuda", "F1"),
)


def default_shortcuts_path() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "Benedito Digital" / "shortcuts.json"


def shortcut_to_tk(value: str) -> str | None:
    modifiers, normalized_key = parse_shortcut(value)
    if normalized_key is None:
        return None
    components = [*modifiers, normalized_key]
    return f"<{ '-'.join(components) }>"


def parse_shortcut(value: str) -> tuple[tuple[str, ...], str | None]:
    parts = [part.strip() for part in str(value).split("+") if part.strip()]
    if not parts:
        return (), None
    modifier_names = {
        "ctrl": "Control",
        "control": "Control",
        "shift": "Shift",
        "alt": "Alt",
    }
    modifiers = []
    key = None
    for part in parts:
        mapped = modifier_names.get(part.lower())
        if mapped:
            if mapped not in modifiers:
                modifiers.append(mapped)
        elif key is None:
            key = part
        else:
            raise ValueError(f"Atalho inválido: {value}")
    if key is None:
        raise ValueError(f"Atalho sem tecla: {value}")
    aliases = {
        "space": "space",
        "delete": "Delete",
        "home": "Home",
        "end": "End",
        "left": "Left",
        "right": "Right",
        "up": "Up",
        "down": "Down",
        "comma": "comma",
        ",": "comma",
        "[": "bracketleft",
        "]": "bracketright",
    }
    normalized_key = aliases.get(key.lower(), key.lower() if len(key) == 1 else key)
    return tuple(modifiers), normalized_key


def shortcut_matches_event(value: str, keysym: str, state: int) -> bool:
    """Match a Tk key event while ignoring Caps Lock and Num Lock state."""
    modifiers, expected_key = parse_shortcut(value)
    if expected_key is None:
        return False
    active_modifiers = set()
    if state & 0x0001:
        active_modifiers.add("Shift")
    if state & 0x0004:
        active_modifiers.add("Control")
    if state & 0x0008 or state & 0x20000:
        active_modifiers.add("Alt")
    if active_modifiers != set(modifiers):
        return False
    event_key = str(keysym or "")
    aliases = {
        ",": "comma",
        "[": "bracketleft",
        "]": "bracketright",
    }
    event_key = aliases.get(event_key, event_key)
    if len(event_key) == 1:
        event_key = event_key.lower()
    if len(expected_key) == 1:
        expected_key = expected_key.lower()
    return event_key.lower() == expected_key.lower()


class ShortcutPreferences:
    VERSION = 1

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_shortcuts_path()
        self.values = {item.action: item.default for item in SHORTCUT_DEFINITIONS}
        self.load()

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        values = data.get("shortcuts", {}) if isinstance(data, dict) else {}
        for definition in SHORTCUT_DEFINITIONS:
            value = values.get(definition.action)
            if isinstance(value, str):
                try:
                    shortcut_to_tk(value)
                except ValueError:
                    continue
                self.values[definition.action] = value.strip()

    def get(self, action: str) -> str:
        return self.values.get(action, "")

    def sequence(self, action: str) -> str | None:
        return shortcut_to_tk(self.get(action))

    def replace(self, values: dict[str, str]):
        normalized = {}
        used = {}
        for definition in SHORTCUT_DEFINITIONS:
            value = str(values.get(definition.action, "")).strip()
            sequence = shortcut_to_tk(value) if value else None
            if sequence and sequence in used:
                raise ValueError(
                    f"{definition.label} usa o mesmo atalho de {used[sequence]}"
                )
            if sequence:
                used[sequence] = definition.label
            normalized[definition.action] = value
        self.values = normalized
        self.save()

    def reset(self):
        self.values = {item.action: item.default for item in SHORTCUT_DEFINITIONS}
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(
                {
                    "version": self.VERSION,
                    "shortcuts": self.values,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
