"""GUI orchestration for perforation-based film registration."""

from __future__ import annotations

import os

import cv2
from tkinter import messagebox

from core.film_analysis import FilmPerforationDetector
from gui.dialogs.film_registration_dialog import FilmRegistrationDialog


class FilmRegistrationController:
    def __init__(self, editor):
        self.editor = editor
        self.detector = FilmPerforationDetector()

    def open_dialog(self):
        editor = self.editor
        if not editor.frame_manager or not editor.frame_manager.frames:
            messagebox.showinfo("Película", "Extraia ou carregue frames primeiro.")
            return
        start, end = self._selected_range()
        FilmRegistrationDialog(editor.root, start + 1, end + 1, lambda mode, confidence: self.apply_range(start, end, mode, confidence))

    def apply_range(self, start, end, reference_mode="first", min_confidence=0.45):
        editor = self.editor
        frames = list(editor.frame_manager.frames)
        indices = list(range(max(0, start), min(end, len(frames) - 1) + 1))
        if len(indices) < 2:
            messagebox.showinfo("Película", "Selecione ao menos dois frames.")
            return

        def registration_task(context):
            os.makedirs(editor.restored_dir, exist_ok=True)
            reference = cv2.imread(editor._get_source_frame_path(indices[0]), cv2.IMREAD_COLOR)
            if reference is None:
                raise RuntimeError("Não foi possível abrir o frame de referência")
            aligned_count = 0
            skipped_count = 0
            measurements = []
            for position, frame_index in enumerate(indices[1:], start=1):
                context.check_cancelled()
                current = cv2.imread(editor._get_source_frame_path(frame_index), cv2.IMREAD_COLOR)
                if current is None:
                    skipped_count += 1
                    continue
                aligned, registration = self.detector.align_to_reference(reference, current)
                measurement = {
                    "frame": frame_index,
                    "translate_x": registration.dx,
                    "translate_y": registration.dy,
                    "confidence": registration.confidence,
                    "matches": registration.matches,
                }
                measurements.append(measurement)
                if registration.confidence < min_confidence or registration.matches < 2:
                    skipped_count += 1
                    if reference_mode == "previous":
                        reference = current
                else:
                    output_path = os.path.join(editor.restored_dir, frames[frame_index])
                    if not cv2.imwrite(output_path, aligned):
                        raise RuntimeError(f"Não foi possível salvar {output_path}")
                    if editor.workspace:
                        editor.workspace.commit_operation(
                            "film.perforation_registration",
                            payload={**measurement, "reference_mode": reference_mode, "minimum_confidence": min_confidence, "border_mode": "replicate"},
                            frame_number=frame_index,
                            artifacts={"result": output_path},
                        )
                    aligned_count += 1
                    if reference_mode == "previous":
                        reference = aligned
                context.report((position + 1) * 100.0 / len(indices), f"Alinhando película — {position + 1}/{len(indices)}")
            return {"aligned": aligned_count, "skipped": skipped_count, "measurements": measurements}

        def registration_complete(result):
            editor.view_mode = "restored"
            editor.show_current_frame()
            editor.status_var.set(f"Película alinhada: {result['aligned']} frames; {result['skipped']} sem confiança suficiente")
            messagebox.showinfo("Registro concluído", f"Frames alinhados: {result['aligned']}\nFrames preservados sem alteração: {result['skipped']}")

        editor._start_ui_job("Registro por perfurações", registration_task, registration_complete)

    def _selected_range(self):
        editor = self.editor
        total = len(editor.frame_manager.frames)
        try:
            start = max(0, int(editor.range_start_entry.get()) - 1)
            end = min(total - 1, int(editor.range_end_entry.get()) - 1)
        except (AttributeError, ValueError):
            start, end = 0, total - 1
        return min(start, end), max(start, end)
