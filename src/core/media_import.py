"""Validated plans for importing complete media or exact working segments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .storage import estimate_lossless_video_bytes


WORKING_FORMATS = {
    "mkv_lossless": {
        "extension": ".mkv",
        "video_codec": "ffv1",
        "audio_codec": "pcm_s24le",
    },
    "mov_prores": {
        "extension": ".mov",
        "video_codec": "prores_ks",
        "audio_codec": "pcm_s24le",
    },
    "mp4_hq": {
        "extension": ".mp4",
        "video_codec": "h264",
        "audio_codec": "aac",
    },
}
AUDIO_MODES = {"preserve", "dual_mono_left", "dual_mono_right", "mono_mix"}


class MediaImportPlanError(ValueError):
    """Raised when an import selection is incomplete or unsafe."""


@dataclass(frozen=True)
class MediaImportSelection:
    mode: str
    start_time: float = 0.0
    end_time: float | None = None

    @property
    def is_segment(self) -> bool:
        return self.mode == "segment"


@dataclass(frozen=True)
class MediaImportPlan:
    mode: str
    source_path: Path
    destination_name: str
    start_time: float = 0.0
    end_time: float | None = None
    estimated_bytes: int = 0
    working_format: str = "mkv_lossless"
    audio_mode: str = "preserve"

    @property
    def is_segment(self) -> bool:
        return self.mode == "segment"

    @property
    def duration(self) -> float | None:
        return None if self.end_time is None else self.end_time - self.start_time


def build_import_selection(
    mode: str,
    *,
    start_value: str = "00:00:00",
    end_value: str = "",
) -> MediaImportSelection:
    """Validate the user's choice before media analysis starts."""
    if mode == "full":
        return MediaImportSelection(mode="full")
    if mode != "segment":
        raise MediaImportPlanError("Escolha filme inteiro ou somente um trecho")
    start = parse_timecode(start_value)
    end = parse_timecode(end_value)
    if end <= start:
        raise MediaImportPlanError("O final do trecho precisa ser posterior ao início")
    return MediaImportSelection(mode="segment", start_time=start, end_time=end)


def build_import_plan(
    source_path,
    mode: str,
    video_info: dict,
    *,
    start_value: str = "0",
    end_value: str = "",
    working_format: str = "mkv_lossless",
    audio_mode: str = "preserve",
) -> MediaImportPlan:
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise MediaImportPlanError("O arquivo de origem não existe")
    if mode == "full":
        return MediaImportPlan(
            mode="full",
            source_path=source,
            destination_name=source.name,
            estimated_bytes=source.stat().st_size,
        )
    if mode != "segment":
        raise MediaImportPlanError("Escolha filme inteiro ou somente um trecho")
    if working_format not in WORKING_FORMATS:
        raise MediaImportPlanError("Escolha um formato de trabalho válido")
    if audio_mode not in AUDIO_MODES:
        raise MediaImportPlanError("Escolha um tratamento de áudio válido")

    total_duration = float(video_info.get("duration", 0) or 0)
    if total_duration <= 0:
        raise MediaImportPlanError("Não foi possível detectar a duração do vídeo")
    start = parse_timecode(start_value)
    end = parse_timecode(end_value)
    if start < 0 or end <= start:
        raise MediaImportPlanError("O final do trecho precisa ser posterior ao início")
    if end > total_duration + 0.05:
        raise MediaImportPlanError("O final do trecho ultrapassa a duração do vídeo")

    destination_name = segment_file_name(source, start, end, working_format)
    estimated = estimate_lossless_video_bytes(
        end - start,
        float(video_info.get("fps", 0) or 0),
        int(video_info.get("width", 0) or 0),
        int(video_info.get("height", 0) or 0),
        source_size=source.stat().st_size,
        source_duration=total_duration,
    )
    return MediaImportPlan(
        mode="segment",
        source_path=source,
        destination_name=destination_name,
        start_time=start,
        end_time=end,
        estimated_bytes=estimated,
        working_format=working_format,
        audio_mode=audio_mode,
    )


def parse_timecode(value: str) -> float:
    text = str(value).strip().replace(",", ".")
    if not text:
        raise MediaImportPlanError("Informe o início e o final do trecho")
    parts = text.split(":")
    if len(parts) > 3 or any(not part for part in parts):
        raise MediaImportPlanError("Use o formato HH:MM:SS, como 00:12:30")
    try:
        values = [float(part) for part in parts]
    except ValueError as error:
        raise MediaImportPlanError("Use o formato HH:MM:SS, como 00:12:30") from error
    if any(value < 0 for value in values):
        raise MediaImportPlanError("O tempo não pode ser negativo")
    if len(values) >= 2 and values[-1] >= 60:
        raise MediaImportPlanError("Os segundos precisam estar entre 0 e 59")
    if len(values) == 3 and values[-2] >= 60:
        raise MediaImportPlanError("Os minutos precisam estar entre 0 e 59")
    multipliers = (1, 60, 3600)
    return sum(value * multipliers[index] for index, value in enumerate(reversed(values)))


def format_timecode(seconds: float, *, milliseconds: bool = False) -> str:
    value = max(0.0, float(seconds))
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    remaining = value % 60
    if milliseconds:
        return f"{hours:02d}:{minutes:02d}:{remaining:06.3f}"
    return f"{hours:02d}:{minutes:02d}:{int(round(remaining)):02d}"


def segment_file_name(
    source: Path,
    start: float,
    end: float,
    working_format: str = "mkv_lossless",
) -> str:
    if working_format not in WORKING_FORMATS:
        raise MediaImportPlanError("Escolha um formato de trabalho válido")
    safe_stem = re.sub(r"[^A-Za-z0-9À-ÿ._-]+", "_", source.stem).strip("._") or "filme"
    start_label = format_timecode(start).replace(":", "-")
    end_label = format_timecode(end).replace(":", "-")
    extension = WORKING_FORMATS[working_format]["extension"]
    return f"{safe_stem}_trecho_{start_label}_a_{end_label}{extension}"
