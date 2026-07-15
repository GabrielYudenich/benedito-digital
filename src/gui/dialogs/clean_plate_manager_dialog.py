"""Clean-plate browser and non-destructive image editor."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from core.clean_plate import compose_plate_layer
from core.retouch import apply_retouch_dab


class CleanPlateManagerDialog:
    def __init__(
        self,
        parent,
        records,
        edit_callback,
        reapply_callback,
        rebuild_callback,
        correction_callback,
    ):
        self.records = list(records)
        self.edit_callback = edit_callback
        self.reapply_callback = reapply_callback
        self.rebuild_callback = rebuild_callback
        self.correction_callback = correction_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Placas limpas do projeto")
        self.window.geometry("1180x700")
        self.window.minsize(900, 600)
        self.window.transient(parent)

        container = ttk.Frame(self.window, padding=20)
        container.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            container,
            text="Placas limpas do projeto",
            font=("Segoe UI", 19, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            container,
            text=(
                "A placa preserva somente o fundo comprovadamente estático. Pessoas e objetos "
                "em movimento ficam transparentes e são protegidos novamente em cada frame."
            ),
            wraplength=900,
        ).pack(anchor=tk.W, pady=(4, 14))

        body = ttk.Panedwindow(container, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)
        list_panel = ttk.Frame(body)
        preview_panel = ttk.Frame(body, padding=(14, 0, 0, 0))
        body.add(list_panel, weight=3)
        body.add(preview_panel, weight=4)

        self.tree = ttk.Treeview(
            list_panel,
            columns=("interval", "static", "changed", "edited"),
            show="tree headings",
            selectmode="browse",
        )
        self.tree.heading("#0", text="Fonte")
        self.tree.heading("interval", text="Frames")
        self.tree.heading("static", text="Fundo estável")
        self.tree.heading("changed", text="Alterados")
        self.tree.heading("edited", text="Edição")
        self.tree.column("#0", width=260)
        self.tree.column("interval", width=110, anchor=tk.CENTER)
        self.tree.column("static", width=100, anchor=tk.CENTER)
        self.tree.column("changed", width=85, anchor=tk.CENTER)
        self.tree.column("edited", width=75, anchor=tk.CENTER)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_panel, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self._show_selected)

        self.preview = ttk.Label(
            preview_panel,
            text="Selecione uma placa para visualizar",
            anchor=tk.CENTER,
        )
        self.preview.pack(fill=tk.BOTH, expand=True)
        self.details_var = tk.StringVar()
        ttk.Label(
            preview_panel,
            textvariable=self.details_var,
            justify=tk.LEFT,
            wraplength=470,
        ).pack(fill=tk.X, pady=(10, 0))

        footer = ttk.Frame(container)
        footer.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(footer, text="Fechar", command=self.window.destroy).pack(side=tk.RIGHT)
        self.folder_button = ttk.Button(footer, text="Abrir pasta", command=self._open_folder)
        self.folder_button.pack(side=tk.LEFT)
        self.edit_button = ttk.Button(footer, text="Editar placa...", command=self._edit)
        self.edit_button.pack(side=tk.LEFT, padx=8)
        self.rebuild_button = ttk.Button(
            footer,
            text="Recriar placa...",
            command=self._rebuild,
        )
        self.rebuild_button.pack(side=tk.LEFT, padx=(0, 8))
        self.reapply_button = ttk.Button(
            footer,
            text="Reaplicar ao trecho",
            command=self._reapply,
        )
        self.reapply_button.pack(side=tk.LEFT)
        self.correction_button = ttk.Button(
            footer,
            text="Corrigir movimento no frame atual...",
            command=self._correct_current_frame,
        )
        self.correction_button.pack(side=tk.LEFT, padx=(8, 0))

        for index, record in enumerate(self.records):
            ratio = float(record.diagnostics.get("static_ratio", 0.0)) * 100.0
            self.tree.insert(
                "",
                tk.END,
                iid=str(index),
                text=os.path.basename(record.source) or record.source,
                values=(
                    f"{record.start + 1}–{record.end + 1}",
                    f"{ratio:.1f}%",
                    f"{record.modified_frames}/{record.frame_count}",
                    "Sim" if record.edited else "Gerada",
                ),
            )
        state = tk.NORMAL if self.records else tk.DISABLED
        for button in (
            self.folder_button,
            self.edit_button,
            self.rebuild_button,
            self.reapply_button,
            self.correction_button,
        ):
            button.configure(state=state)
        if self.records:
            self.tree.selection_set("0")
            self.tree.focus("0")
            self._show_selected()
        else:
            self.details_var.set("Nenhuma placa limpa foi criada nesta área de trabalho.")

    def selected_record(self):
        selection = self.tree.selection()
        return self.records[int(selection[0])] if selection else None

    def _show_selected(self, _event=None):
        record = self.selected_record()
        if record is None:
            return
        try:
            preview_path = record.transparent_plate_path or record.plate_path
            with Image.open(preview_path) as image:
                preview = image.convert("RGBA")
                preview.thumbnail((490, 390), Image.Resampling.LANCZOS)
                checker = Image.new("RGB", preview.size, (54, 48, 63))
                pixels = checker.load()
                square = 14
                for y in range(preview.height):
                    for x in range(preview.width):
                        if (x // square + y // square) % 2:
                            pixels[x, y] = (80, 72, 92)
                checker.paste(preview, mask=preview.getchannel("A"))
                photo = ImageTk.PhotoImage(checker)
        except Exception:
            self.preview.configure(image="", text="Não foi possível abrir a placa")
            self.preview.image = None
            return
        self.preview.configure(image=photo, text="")
        self.preview.image = photo
        motion = float(record.diagnostics.get("mean_camera_motion", 0.0))
        ratio = float(record.diagnostics.get("static_ratio", 0.0)) * 100.0
        sharpness = record.diagnostics.get("plate_sharpness")
        quality = (
            f"Nitidez da placa: {float(sharpness):.1f}\n"
            if sharpness is not None
            else "Placa antiga: recrie o mesmo trecho para usar a nova base nítida.\n"
        )
        transparency = (
            "Movimento: transparente na placa RGBA\n"
            if record.transparent_plate_path
            else "Placa antiga sem alpha: recrie para tornar movimento transparente.\n"
        )
        layer_status = (
            "Camada não destrutiva: ativa — correções podem revelar o original\n"
            if record.layer_metadata_path and record.layer_metadata_path.is_file()
            else "Camada não destrutiva: ainda não aplicada\n"
        )
        self.details_var.set(
            f"ID: {record.plate_id}\n"
            f"Trecho: frames {record.start + 1}–{record.end + 1} "
            f"({record.frame_count} frames)\n"
            f"Fundo estável: {ratio:.1f}%  •  movimento médio: {motion:.2f} px\n"
            f"{quality}"
            f"{transparency}"
            f"{layer_status}"
            f"Frames efetivamente alterados: {record.modified_frames}\n"
            f"Arquivo: {record.plate_path}"
        )

    def _open_folder(self):
        record = self.selected_record()
        if record is None:
            return
        path = str(record.directory)
        if os.name == "nt":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _edit(self):
        record = self.selected_record()
        if record is None:
            return
        self.edit_callback(
            record,
            self.window,
            lambda reapply=False, edited_record=record: self._plate_edited(
                edited_record, reapply
            ),
        )

    def _plate_edited(self, record, reapply=False):
        self._show_selected()
        item = self.tree.selection()
        if item:
            values = list(self.tree.item(item[0], "values"))
            values[3] = "Sim"
            self.tree.item(item[0], values=values)
        if reapply:
            CleanPlateApplicationDialog(
                self.window,
                record,
                lambda mode: self.reapply_callback(record, mode),
            )

    def _reapply(self):
        record = self.selected_record()
        if record is None:
            return
        CleanPlateApplicationDialog(
            self.window,
            record,
            lambda mode: self.reapply_callback(record, mode),
        )

    def _rebuild(self):
        record = self.selected_record()
        if record is not None:
            self.rebuild_callback(record)

    def _correct_current_frame(self):
        record = self.selected_record()
        if record is not None:
            self.correction_callback(record, self.window)


class CleanPlateApplicationDialog:
    def __init__(self, parent, record, apply_callback):
        self.apply_callback = apply_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Como reaplicar a placa?")
        self.window.geometry("650x430")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        container = ttk.Frame(self.window, padding=22)
        container.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            container,
            text="Aplicar placa limpa",
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            container,
            text=f"Trecho: frames {record.start + 1}–{record.end + 1}",
        ).pack(anchor=tk.W, pady=(3, 16))

        self.mode_var = tk.StringVar(value="background")
        visible = ttk.LabelFrame(container, text="Resultado visível — recomendado", padding=12)
        visible.pack(fill=tk.X)
        ttk.Radiobutton(
            visible,
            text="Reconstruir todo o fundo considerado estático",
            variable=self.mode_var,
            value="background",
        ).pack(anchor=tk.W)
        ttk.Label(
            visible,
            text=(
                "Usa a placa em toda a área estática e protege pessoas ou objetos em "
                "movimento. O alinhamento preciso corrige translação, rotação e pequenas "
                "diferenças de escala em cada frame."
            ),
            wraplength=560,
        ).pack(anchor=tk.W, padx=(22, 0), pady=(5, 0))

        conservative = ttk.LabelFrame(container, text="Retoque conservador", padding=12)
        conservative.pack(fill=tk.X, pady=(12, 0))
        ttk.Radiobutton(
            conservative,
            text="Substituir somente poeira e riscos detectados",
            variable=self.mode_var,
            value="defects",
        ).pack(anchor=tk.W)
        ttk.Label(
            conservative,
            text="Pode alterar poucos frames e produzir uma diferença quase imperceptível.",
            wraplength=560,
        ).pack(anchor=tk.W, padx=(22, 0), pady=(5, 0))

        footer = ttk.Frame(container)
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(16, 0))
        ttk.Button(footer, text="Cancelar", command=self.window.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Aplicar ao trecho", command=self._apply).pack(side=tk.RIGHT, padx=8)

    def _apply(self):
        mode = self.mode_var.get()
        self.window.destroy()
        self.apply_callback(mode)


class CleanPlateRevealDialog:
    def __init__(
        self,
        parent,
        frame_number,
        source_path,
        composite_path,
        reveal_mask_path,
        save_callback,
    ):
        self.source = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
        self.composite = cv2.imread(str(composite_path), cv2.IMREAD_COLOR)
        if self.source is None or self.composite is None:
            raise RuntimeError("A camada ou o frame-base não pôde ser aberto")
        if self.source.shape[:2] != self.composite.shape[:2]:
            self.source = cv2.resize(
                self.source,
                (self.composite.shape[1], self.composite.shape[0]),
                interpolation=cv2.INTER_CUBIC,
            )
        existing = (
            cv2.imread(str(reveal_mask_path), cv2.IMREAD_GRAYSCALE)
            if os.path.isfile(reveal_mask_path)
            else None
        )
        self.reveal_mask = (
            cv2.resize(
                existing,
                (self.composite.shape[1], self.composite.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )
            if existing is not None
            else np.zeros(self.composite.shape[:2], dtype=np.uint8)
        )
        self.save_callback = save_callback
        self.undo_stack = []
        self.redo_stack = []
        self.last_point = None
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self.pan_start = None
        self.pan_origin = None
        self.photo = None
        self.redraw_job = None

        self.window = tk.Toplevel(parent)
        self.window.title(f"Corrigir camada da placa — frame {frame_number}")
        self.window.geometry("1280x820")
        self.window.minsize(1000, 650)
        self.window.transient(parent)

        toolbar = ttk.Frame(self.window, padding=10)
        toolbar.pack(fill=tk.X)
        self.tool_var = tk.StringVar(value="reveal")
        ttk.Radiobutton(
            toolbar,
            text="◉ Revelar frame original",
            variable=self.tool_var,
            value="reveal",
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            toolbar,
            text="▣ Restaurar camada da placa",
            variable=self.tool_var,
            value="restore",
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(toolbar, text="Pincel:").pack(side=tk.LEFT, padx=(18, 5))
        self.brush_size = tk.IntVar(value=28)
        ttk.Scale(
            toolbar,
            from_=3,
            to=180,
            variable=self.brush_size,
            orient=tk.HORIZONTAL,
            length=170,
        ).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Desfazer", command=self._undo).pack(side=tk.LEFT, padx=(16, 4))
        ttk.Button(toolbar, text="Refazer", command=self._redo).pack(side=tk.LEFT)

        self.preview_mode = tk.StringVar(value="corrected")
        self.show_reveal_overlay = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            toolbar,
            text="Mostrar máscara amarela",
            variable=self.show_reveal_overlay,
            command=self._schedule_redraw,
        ).pack(side=tk.RIGHT, padx=(12, 0))
        for value, label in (
            ("corrected", "Com correção"),
            ("composite", "Somente placa"),
            ("source", "Camada inferior"),
        ):
            ttk.Radiobutton(
                toolbar,
                text=label,
                variable=self.preview_mode,
                value=value,
                command=self._schedule_redraw,
            ).pack(side=tk.RIGHT, padx=(7, 0))

        self.canvas = tk.Canvas(
            self.window,
            bg="#08060d",
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10)
        self.canvas.bind("<Configure>", self._schedule_redraw)
        self.canvas.bind("<ButtonPress-1>", self._paint_start)
        self.canvas.bind("<B1-Motion>", self._paint_move)
        self.canvas.bind("<ButtonRelease-1>", self._paint_end)
        self.canvas.bind("<ButtonPress-2>", self._pan_start)
        self.canvas.bind("<B2-Motion>", self._pan_move)
        self.canvas.bind("<MouseWheel>", self._zoom_wheel)

        footer = ttk.Frame(self.window, padding=10)
        footer.pack(fill=tk.X)
        ttk.Label(
            footer,
            text=(
                "Pinte sobre braços, rostos ou objetos apagados: o resultado aparece "
                "imediatamente. Ative a máscara amarela apenas para conferir a área."
            ),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(footer, text="Cancelar", command=self.window.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Salvar correção", command=self._save).pack(side=tk.RIGHT, padx=8)
        ttk.Button(footer, text="Ajustar à janela", command=self._fit).pack(side=tk.RIGHT)
        self._schedule_redraw()

    def _view_transform(self):
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        image_height, image_width = self.composite.shape[:2]
        fit = min(width / image_width, height / image_height)
        scale = max(0.02, fit * self.zoom)
        left = (width - image_width * scale) / 2.0 + self.pan[0]
        top = (height - image_height * scale) / 2.0 + self.pan[1]
        return scale, left, top

    def _image_point(self, event):
        scale, left, top = self._view_transform()
        x = int(round((event.x - left) / scale))
        y = int(round((event.y - top) / scale))
        if 0 <= x < self.composite.shape[1] and 0 <= y < self.composite.shape[0]:
            return x, y
        return None

    def _paint_start(self, event):
        point = self._image_point(event)
        if point is None:
            return
        self.undo_stack.append(self.reveal_mask.copy())
        del self.undo_stack[:-20]
        self.redo_stack.clear()
        self.last_point = point
        self._paint(point)

    def _paint_move(self, event):
        point = self._image_point(event)
        if point is None or self.last_point is None:
            return
        self._paint(point)
        self.last_point = point

    def _paint_end(self, _event):
        self.last_point = None

    def _paint(self, point):
        value = 255 if self.tool_var.get() == "reveal" else 0
        radius = max(2, int(self.brush_size.get()))
        if self.last_point is None:
            cv2.circle(self.reveal_mask, point, radius, value, -1, cv2.LINE_AA)
        else:
            cv2.line(
                self.reveal_mask,
                self.last_point,
                point,
                value,
                radius * 2,
                cv2.LINE_AA,
            )
        self._schedule_redraw()

    def _undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(self.reveal_mask.copy())
        self.reveal_mask = self.undo_stack.pop()
        self._schedule_redraw()

    def _redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(self.reveal_mask.copy())
        self.reveal_mask = self.redo_stack.pop()
        self._schedule_redraw()

    def _pan_start(self, event):
        self.pan_start = (event.x, event.y)
        self.pan_origin = tuple(self.pan)

    def _pan_move(self, event):
        if self.pan_start is None:
            return
        self.pan[0] = self.pan_origin[0] + event.x - self.pan_start[0]
        self.pan[1] = self.pan_origin[1] + event.y - self.pan_start[1]
        self._schedule_redraw()

    def _zoom_wheel(self, event):
        self.zoom = min(8.0, max(0.35, self.zoom * (1.14 if event.delta > 0 else 1 / 1.14)))
        self._schedule_redraw()

    def _fit(self):
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self._schedule_redraw()

    def _schedule_redraw(self, _event=None):
        if self.redraw_job is None:
            self.redraw_job = self.window.after(16, self._redraw)

    def _redraw(self):
        self.redraw_job = None
        scale, left, top = self._view_transform()
        width = max(1, int(round(self.composite.shape[1] * scale)))
        height = max(1, int(round(self.composite.shape[0] * scale)))
        source = cv2.resize(self.source, (width, height), interpolation=cv2.INTER_AREA)
        composite = cv2.resize(self.composite, (width, height), interpolation=cv2.INTER_AREA)
        mask = cv2.resize(self.reveal_mask, (width, height), interpolation=cv2.INTER_NEAREST)
        mode = self.preview_mode.get()
        if mode == "source":
            display = source
        elif mode == "composite":
            display = composite
        else:
            display = compose_plate_layer(source, composite, mask, feather=max(0.6, 3.0 * scale))
            if np.any(mask) and self.show_reveal_overlay.get():
                overlay = display.copy()
                overlay[mask > 0] = (30, 205, 255)
                display = cv2.addWeighted(display, 0.72, overlay, 0.28, 0)
        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        self.photo = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.canvas.delete("all")
        self.canvas.create_image(left, top, image=self.photo, anchor=tk.NW)

    def _save(self):
        try:
            self.save_callback(self.reveal_mask.copy())
        except Exception as exc:
            messagebox.showerror("Salvar correção", str(exc), parent=self.window)
            return
        self.window.destroy()


class CleanPlateEditorDialog:
    def __init__(self, parent, record, save_callback, on_saved=None):
        self.record = record
        self.save_callback = save_callback
        self.on_saved = on_saved
        self.image = cv2.imread(str(record.plate_path), cv2.IMREAD_COLOR)
        self.static_mask = cv2.imread(str(record.static_mask_path), cv2.IMREAD_GRAYSCALE)
        if self.image is None:
            raise RuntimeError(f"Não foi possível abrir {record.plate_path}")
        if self.static_mask is None:
            self.static_mask = np.full(self.image.shape[:2], 255, dtype=np.uint8)
        elif self.static_mask.shape != self.image.shape[:2]:
            self.static_mask = cv2.resize(
                self.static_mask,
                (self.image.shape[1], self.image.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )
        self.noise_mask = np.zeros(self.image.shape[:2], dtype=np.uint8)
        self.undo_stack = []
        self.redo_stack = []
        self.tool = "noise"
        self.source_anchor = None
        self.target_anchor = None
        self.stroke_source = None
        self.last_point = None
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self.pan_start = None
        self.pan_origin = None
        self.photo = None
        self.redraw_job = None

        self.window = tk.Toplevel(parent)
        self.window.title(f"Editar placa limpa — frames {record.start + 1}–{record.end + 1}")
        self.window.geometry("1240x820")
        self.window.minsize(900, 650)
        self.window.transient(parent)

        toolbar = ttk.Frame(self.window, padding=10)
        toolbar.pack(fill=tk.X)
        self.tool_buttons = {}
        for tool, label in (
            ("noise", "✦ Marcar ruído"),
            ("clone", "▣ Clone"),
            ("heal", "+ Healing"),
        ):
            button = ttk.Button(toolbar, text=label, command=lambda value=tool: self._set_tool(value))
            button.pack(side=tk.LEFT, padx=(0, 6))
            self.tool_buttons[tool] = button
        ttk.Button(toolbar, text="Remover ruído marcado", command=self._inpaint_noise).pack(side=tk.LEFT, padx=(8, 6))
        ttk.Button(toolbar, text="Desfazer", command=self._undo).pack(side=tk.LEFT, padx=(8, 4))
        ttk.Button(toolbar, text="Refazer", command=self._redo).pack(side=tk.LEFT)
        ttk.Label(toolbar, text="Pincel:").pack(side=tk.LEFT, padx=(18, 5))
        self.brush_size = tk.IntVar(value=18)
        ttk.Scale(toolbar, from_=2, to=120, variable=self.brush_size, orient=tk.HORIZONTAL, length=150).pack(side=tk.LEFT)

        alpha_toolbar = ttk.Frame(self.window, padding=(10, 0, 10, 8))
        alpha_toolbar.pack(fill=tk.X)
        ttk.Label(alpha_toolbar, text="Transparência da placa:").pack(side=tk.LEFT)
        for tool, label in (
            ("transparent", "◫ Tornar transparente"),
            ("static", "▣ Manter como fundo"),
        ):
            button = ttk.Button(
                alpha_toolbar,
                text=label,
                command=lambda value=tool: self._set_tool(value),
            )
            button.pack(side=tk.LEFT, padx=(8, 0))
            self.tool_buttons[tool] = button
        self.mask_overlay = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            alpha_toolbar,
            text="Prévia quadriculada da transparência",
            variable=self.mask_overlay,
            command=self._schedule_redraw,
        ).pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(self.window, bg="#08060d", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10)
        self.canvas.bind("<Configure>", self._schedule_redraw)
        self.canvas.bind("<ButtonPress-1>", self._left_press)
        self.canvas.bind("<B1-Motion>", self._left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._left_release)
        self.canvas.bind("<Button-3>", self._set_source)
        self.canvas.bind("<ButtonPress-2>", self._pan_press)
        self.canvas.bind("<B2-Motion>", self._pan_drag)
        self.canvas.bind("<MouseWheel>", self._zoom_wheel)

        footer = ttk.Frame(self.window, padding=10)
        footer.pack(fill=tk.X)
        self.status_var = tk.StringVar()
        ttk.Label(footer, textvariable=self.status_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(footer, text="Cancelar", command=self.window.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Salvar placa", command=self._save).pack(side=tk.RIGHT, padx=8)
        ttk.Button(footer, text="Ajustar à janela", command=self._fit).pack(side=tk.RIGHT)
        self._set_tool("noise")
        self._schedule_redraw()

    def _set_tool(self, tool):
        self.tool = tool
        if tool == "noise":
            message = "Pinte poeira e riscos; depois clique em Remover ruído marcado."
        elif tool == "transparent":
            message = "Pinte as áreas que não devem fazer parte da placa; elas ficarão transparentes."
        elif tool == "static":
            message = "Pinte para restaurar uma área transparente como fundo estático da placa."
        else:
            message = "Botão direito define a origem; arraste com o esquerdo para retocar."
        self.status_var.set(message)

    def _view_transform(self):
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        image_height, image_width = self.image.shape[:2]
        fit = min(width / image_width, height / image_height)
        scale = max(0.02, fit * self.zoom)
        left = (width - image_width * scale) / 2.0 + self.pan[0]
        top = (height - image_height * scale) / 2.0 + self.pan[1]
        return scale, left, top

    def _image_point(self, event):
        scale, left, top = self._view_transform()
        x = int(round((event.x - left) / scale))
        y = int(round((event.y - top) / scale))
        if 0 <= x < self.image.shape[1] and 0 <= y < self.image.shape[0]:
            return x, y
        return None

    def _push_undo(self):
        self.undo_stack.append(
            (self.image.copy(), self.noise_mask.copy(), self.static_mask.copy())
        )
        del self.undo_stack[:-16]
        self.redo_stack.clear()

    def _left_press(self, event):
        point = self._image_point(event)
        if point is None:
            return
        if self.tool in {"clone", "heal"} and self.source_anchor is None:
            self.status_var.set("Defina primeiro uma origem com o botão direito.")
            return
        self._push_undo()
        self.last_point = point
        self.target_anchor = point
        self.stroke_source = self.image.copy()
        self._apply_point(point)

    def _left_drag(self, event):
        point = self._image_point(event)
        if point is None or self.last_point is None:
            return
        for interpolated in self._interpolate(self.last_point, point):
            self._apply_point(interpolated)
        self.last_point = point

    def _left_release(self, _event):
        self.last_point = None
        self.target_anchor = None
        self.stroke_source = None

    def _apply_point(self, point):
        radius = max(2, int(self.brush_size.get()))
        if self.tool == "noise":
            if self.last_point is None:
                cv2.circle(self.noise_mask, point, radius, 255, -1, cv2.LINE_AA)
            else:
                cv2.line(self.noise_mask, self.last_point, point, 255, radius * 2, cv2.LINE_AA)
        elif self.tool in {"transparent", "static"}:
            value = 0 if self.tool == "transparent" else 255
            if self.last_point is None:
                cv2.circle(self.static_mask, point, radius, value, -1, cv2.LINE_AA)
            else:
                cv2.line(
                    self.static_mask,
                    self.last_point,
                    point,
                    value,
                    radius * 2,
                    cv2.LINE_AA,
                )
        else:
            source = (
                self.source_anchor[0] + point[0] - self.target_anchor[0],
                self.source_anchor[1] + point[1] - self.target_anchor[1],
            )
            self.image = apply_retouch_dab(
                self.image,
                source,
                point,
                radius,
                mode=self.tool,
                hardness=0.7,
                source_image=self.stroke_source,
            )
        self._schedule_redraw()

    @staticmethod
    def _interpolate(start, end):
        distance = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
        steps = max(1, distance // 3)
        return [
            (
                int(round(start[0] + (end[0] - start[0]) * step / steps)),
                int(round(start[1] + (end[1] - start[1]) * step / steps)),
            )
            for step in range(1, steps + 1)
        ]

    def _set_source(self, event):
        point = self._image_point(event)
        if point is not None:
            self.source_anchor = point
            self.status_var.set(f"Origem definida em x={point[0]}, y={point[1]}.")
            self._schedule_redraw()

    def _inpaint_noise(self):
        if not np.any(self.noise_mask):
            messagebox.showinfo("Remover ruído", "Pinte primeiro os ruídos que deseja remover.", parent=self.window)
            return
        self._push_undo()
        radius = max(2, min(15, int(self.brush_size.get()) // 3))
        self.image = cv2.inpaint(self.image, self.noise_mask, radius, cv2.INPAINT_TELEA)
        self.noise_mask.fill(0)
        self.status_var.set("Ruído removido. Revise a placa e salve quando estiver satisfeito.")
        self._schedule_redraw()

    def _undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(
            (self.image.copy(), self.noise_mask.copy(), self.static_mask.copy())
        )
        self.image, self.noise_mask, self.static_mask = self.undo_stack.pop()
        self._schedule_redraw()

    def _redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(
            (self.image.copy(), self.noise_mask.copy(), self.static_mask.copy())
        )
        self.image, self.noise_mask, self.static_mask = self.redo_stack.pop()
        self._schedule_redraw()

    def _pan_press(self, event):
        self.pan_start = (event.x, event.y)
        self.pan_origin = tuple(self.pan)

    def _pan_drag(self, event):
        if self.pan_start is None:
            return
        self.pan[0] = self.pan_origin[0] + event.x - self.pan_start[0]
        self.pan[1] = self.pan_origin[1] + event.y - self.pan_start[1]
        self._schedule_redraw()

    def _zoom_wheel(self, event):
        self.zoom = min(8.0, max(0.35, self.zoom * (1.14 if event.delta > 0 else 1 / 1.14)))
        self._schedule_redraw()

    def _fit(self):
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self._schedule_redraw()

    def _schedule_redraw(self, _event=None):
        if self.redraw_job is None:
            self.redraw_job = self.window.after(16, self._redraw)

    def _redraw(self):
        self.redraw_job = None
        scale, left, top = self._view_transform()
        width = max(1, int(round(self.image.shape[1] * scale)))
        height = max(1, int(round(self.image.shape[0] * scale)))
        display = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
        if self.mask_overlay.get():
            checker = np.zeros_like(display)
            tile = 24
            rows, columns = np.indices(self.static_mask.shape)
            light = ((rows // tile) + (columns // tile)) % 2 == 0
            checker[light] = (92, 92, 102)
            checker[~light] = (42, 42, 52)
            alpha = self.static_mask.astype(np.float32) / 255.0
            display = (
                display.astype(np.float32) * alpha[..., None]
                + checker.astype(np.float32) * (1.0 - alpha[..., None])
            ).astype(np.uint8)
        if np.any(self.noise_mask):
            display = display.copy()
            display[self.noise_mask > 0] = (255, 190, 35)
        pil_image = Image.fromarray(display).resize((width, height), Image.Resampling.BILINEAR)
        self.photo = ImageTk.PhotoImage(pil_image)
        self.canvas.delete("all")
        self.canvas.create_image(left, top, image=self.photo, anchor=tk.NW)
        if self.source_anchor is not None:
            radius = max(4, int(self.brush_size.get() * scale))
            x = left + self.source_anchor[0] * scale
            y = top + self.source_anchor[1] * scale
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline="#38bdf8", width=2)
            self.canvas.create_line(x - radius, y, x + radius, y, fill="#38bdf8", width=1)
            self.canvas.create_line(x, y - radius, x, y + radius, fill="#38bdf8", width=1)

    def _save(self):
        try:
            original_path = self.record.directory / "plate_original.png"
            original_mask_path = (
                self.record.directory / "static_background_original.png"
            )
            if not original_path.exists():
                shutil.copy2(self.record.plate_path, original_path)
            if not original_mask_path.exists() and self.record.static_mask_path.exists():
                shutil.copy2(self.record.static_mask_path, original_mask_path)
            temporary = self.record.directory / "plate.editing.png"
            temporary_mask = self.record.directory / "static_background.editing.png"
            if not cv2.imwrite(str(temporary), self.image):
                raise RuntimeError("Não foi possível gravar a imagem editada")
            if not cv2.imwrite(str(temporary_mask), self.static_mask):
                temporary.unlink(missing_ok=True)
                raise RuntimeError("Não foi possível gravar a transparência editada")
            os.replace(temporary, self.record.plate_path)
            os.replace(temporary_mask, self.record.static_mask_path)
            self.save_callback(self.record, original_path)
        except Exception as exc:
            messagebox.showerror("Salvar placa", str(exc), parent=self.window)
            return
        parent = self.window.master
        self.window.destroy()
        reapply = messagebox.askyesno(
            "Placa salva",
            "A placa e sua transparência foram salvas.\n\n"
            "Os frames já aplicados ainda usam o composite anterior. Deseja reaplicar "
            "a placa ao trecho agora?",
            parent=parent,
        )
        if self.on_saved:
            self.on_saved(reapply)
