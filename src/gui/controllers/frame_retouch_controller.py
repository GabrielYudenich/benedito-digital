"""Controller for interactive clone and healing operations on the frame canvas."""

from __future__ import annotations

import os
from tkinter import messagebox

import cv2

from core.retouch import apply_retouch_dab


class FrameRetouchController:
    def __init__(self, editor):
        self.editor = editor
        self.source = None
        self.source_frame = None
        self.active_stroke = None
        self.original = None
        self.working = None

    def set_source(self, event):
        info = self._frame_info()
        if not info:
            return
        self.source = self.editor._canvas_to_image(
            event.x, event.y, (info["width"], info["height"])
        )
        self.source_frame = info["index"]
        self.editor.status_var.set(
            f"Fonte definida em {self.source}. Agora arraste com o botão esquerdo."
        )
        self.editor.show_current_frame()

    def draw_source_marker(self, info):
        if (
            self.source is None
            or self.source_frame != info.get("index")
            or getattr(self.editor, "selected_tool", "") not in {"clone", "heal"}
        ):
            return
        x = self.source[0] * self.editor._view_scale + self.editor._view_offset[0]
        y = self.source[1] * self.editor._view_scale + self.editor._view_offset[1]
        radius = max(6, self.editor.brush_size * self.editor._view_scale)
        canvas = self.editor.frame_canvas
        canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            outline="#28d7ff", width=2, dash=(5, 3), tags="retouch_source",
        )
        canvas.create_line(x - 7, y, x + 7, y, fill="#28d7ff", width=2)
        canvas.create_line(x, y - 7, x, y + 7, fill="#28d7ff", width=2)

    def start(self, event, mode):
        info = self._frame_info()
        if not info:
            return
        if self.source is None or self.source_frame != info["index"]:
            self.editor.status_var.set(
                "Clone/Healing: clique com o botão direito para definir a fonte."
            )
            return
        restored_path = os.path.join(self.editor.restored_dir, info["filename"])
        source_path = restored_path if os.path.exists(restored_path) else info["path"]
        image = cv2.imread(source_path, cv2.IMREAD_COLOR)
        if image is None:
            messagebox.showerror("Retoque", "Não foi possível abrir o frame atual.")
            return
        self.editor._push_undo_current(f"{mode}.stroke")
        target = self.editor._canvas_to_image(
            event.x, event.y, (info["width"], info["height"])
        )
        self.original = image.copy()
        self.working = image.copy()
        self.active_stroke = {
            "tool": mode,
            "source_anchor": list(self.source),
            "target_anchor": list(target),
            "radius": int(self.editor.brush_size),
            "opacity": 1.0 if mode == "clone" else 0.9,
            "hardness": 0.68,
            "points": [],
        }
        self._append_point(target, info)

    def move(self, event):
        stroke = self.active_stroke
        info = self._frame_info()
        if not stroke or not info:
            return
        point = self.editor._canvas_to_image(
            event.x, event.y, (info["width"], info["height"])
        )
        if stroke["points"]:
            previous = stroke["points"][-1]
            minimum = max(1, int(stroke["radius"] * 0.2))
            if (point[0] - previous[0]) ** 2 + (point[1] - previous[1]) ** 2 < minimum ** 2:
                return
        self._append_point(point, info)

    def finish(self, _event=None):
        stroke = self.active_stroke
        working = self.working
        self.active_stroke = None
        self.original = None
        self.working = None
        if not stroke or not stroke["points"] or working is None:
            return
        info = self._frame_info()
        if not info:
            return
        os.makedirs(self.editor.restored_dir, exist_ok=True)
        output_path = os.path.join(self.editor.restored_dir, info["filename"])
        if not cv2.imwrite(output_path, working):
            messagebox.showerror("Retoque", "Não foi possível salvar o frame retocado.")
            return
        if self.editor.workspace:
            self.editor.workspace.commit_operation(
                "clone.stroke" if stroke["tool"] == "clone" else "heal.stroke",
                payload=stroke,
                frame_number=info["index"],
                artifacts={"frame": output_path},
            )
        self.editor.view_mode = "restored"
        self.editor.view_mode_label.config(text="Visualizacao: restaurado")
        self.editor.show_current_frame()
        label = "Clone" if stroke["tool"] == "clone" else "Healing"
        self.editor.status_var.set(f"{label} salvo no frame {info['index'] + 1}")

    def reset_for_branch(self):
        self.source = None
        self.source_frame = None
        self.active_stroke = None
        self.original = None
        self.working = None

    def _append_point(self, point, info):
        stroke = self.active_stroke
        if not stroke or self.working is None:
            return
        target_anchor = stroke["target_anchor"]
        source_anchor = stroke["source_anchor"]
        source_point = (
            source_anchor[0] + point[0] - target_anchor[0],
            source_anchor[1] + point[1] - target_anchor[1],
        )
        before = self.working
        candidate = apply_retouch_dab(
            before,
            source_point,
            point,
            stroke["radius"],
            mode=stroke["tool"],
            opacity=stroke["opacity"],
            hardness=stroke["hardness"],
            source_image=self.original,
        )
        selection = self.editor._load_selection(info["path"])
        if selection is not None:
            selection_mask = selection > 0
            candidate[~selection_mask] = before[~selection_mask]
        self.working = candidate
        stroke["points"].append([int(point[0]), int(point[1])])
        self._show_preview(candidate, info)

    def _show_preview(self, bgr_image, info):
        from PIL import Image

        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        canvas = self.editor.frame_canvas
        photo = self.editor._photo_from_pil(
            image, canvas.winfo_width(), canvas.winfo_height()
        )
        if photo:
            canvas.delete("all")
            canvas.create_image(
                canvas.winfo_width() // 2,
                canvas.winfo_height() // 2,
                image=photo,
            )
            canvas.image = photo
            self.draw_source_marker(info)

    def _frame_info(self):
        if not self.editor.frame_manager:
            return None
        return self.editor.frame_manager.get_current_frame_info()
