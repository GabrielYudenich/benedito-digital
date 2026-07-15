"""GUI orchestration for the open multipista timeline."""

import json
import subprocess
from pathlib import Path

from tkinter import messagebox

from core.edit_timeline import EditTimeline
from core.paths import executable_path
from gui.dialogs.timeline_dialog import TimelineDialog
from lib.modules.video.renderer.timeline_renderer import TimelineRenderer


class TimelineController:
    def __init__(self, editor):
        self.editor = editor
        self.renderer = TimelineRenderer()

    @property
    def timeline_path(self):
        return Path(self.editor.workspace.metadata_dir) / "timeline.json"

    def open_dialog(self):
        try:
            timeline = EditTimeline.load(self.timeline_path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Timeline", f"A timeline não pôde ser aberta: {error}")
            return
        TimelineDialog(
            self.editor.root,
            timeline,
            self.save,
            self.probe_media,
            self.render,
            initial_source=getattr(self.editor, "current_video_path", None),
        )

    def probe_media(self, path):
        duration = self.editor.video_processor.get_video_duration(path)
        result = subprocess.run(
            [executable_path("ffprobe"), "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        stream_types = set()
        if result.returncode == 0:
            try:
                stream_types = {item.get("codec_type") for item in json.loads(result.stdout).get("streams", [])}
            except json.JSONDecodeError:
                pass
        return {"duration": duration, "has_video": "video" in stream_types, "has_audio": "audio" in stream_types}

    def save(self, timeline):
        timeline.save(self.timeline_path)
        if self.editor.workspace:
            self.editor.workspace.commit_operation(
                "timeline.edit",
                payload={
                    "duration": timeline.duration,
                    "tracks": len(timeline.tracks),
                    "clips": len(timeline.clips),
                    "transitions": len(timeline.transitions),
                },
                artifacts={"timeline": self.timeline_path},
            )
        self.editor.status_var.set(f"Timeline salva: {len(timeline.clips)} clipes")

    def render(self, timeline, output_path):
        def task(context):
            return self.renderer.render(
                timeline,
                output_path,
                progress_callback=lambda value: context.report(value, f"Renderizando timeline — {value:.0f}%"),
                cancel_callback=lambda: context.cancellation_requested,
            )

        def complete(path):
            self.editor.status_var.set(f"Timeline renderizada: {path}")
            messagebox.showinfo("Timeline concluída", f"Vídeo salvo em:\n{path}")

        self.editor._start_ui_job("Renderização da timeline", task, complete)
