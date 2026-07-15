"""Accessible visual non-linear timeline."""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from gui.dialogs.keyframe_editor_dialog import KeyframeEditorDialog


class TimelineDialog:
    def __init__(self, parent, timeline, save_callback, probe_callback, render_callback, initial_source=None):
        self.timeline = timeline
        self.save_callback = save_callback
        self.probe_callback = probe_callback
        self.render_callback = render_callback
        self.initial_source = initial_source
        self.window = tk.Toplevel(parent)
        self.window.title("Timeline multipista")
        self.window.geometry("1180x720")
        self.window.minsize(920, 600)
        self.window.transient(parent)
        self.window.configure(bg="#17131f")

        header = tk.Frame(self.window, bg="#17131f")
        header.pack(fill=tk.X, padx=20, pady=(18, 10))
        tk.Label(header, text="Timeline multipista", font=("Segoe UI", 21, "bold"), fg="#f5f3f7", bg="#17131f").pack(side=tk.LEFT)
        self.summary_var = tk.StringVar()
        tk.Label(header, textvariable=self.summary_var, fg="#b8afc4", bg="#17131f").pack(side=tk.RIGHT)

        toolbar = tk.Frame(self.window, bg="#241c31", padx=10, pady=10)
        toolbar.pack(fill=tk.X, padx=20)
        for text, command in (
            ("Adicionar mídia", self._add_media),
            ("Adicionar vídeo atual", self._add_initial_source),
            ("Nova trilha", self._add_track),
            ("Editar clipe", self._edit_clip),
            ("Dividir", self._split_clip),
            ("Transição", self._add_transition),
            ("Keyframes", self._keyframes),
            ("Remover", self._remove_clip),
        ):
            ttk.Button(toolbar, text=text, command=command).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="Renderizar timeline", command=self._render).pack(side=tk.RIGHT, padx=3)

        self.canvas = tk.Canvas(self.window, height=250, bg="#101018", highlightthickness=0)
        self.canvas.pack(fill=tk.X, padx=20, pady=(12, 8))
        self.canvas.bind("<Configure>", lambda _event: self._draw_timeline())

        table_frame = tk.Frame(self.window, bg="#17131f")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        self.tree = ttk.Treeview(table_frame, columns=("track", "start", "in", "out", "duration"), show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="Clipe")
        for column, title in (("track", "Trilha"), ("start", "Início"), ("in", "Entrada"), ("out", "Saída"), ("duration", "Duração")):
            self.tree.heading(column, text=title)
        self.tree.column("#0", width=260)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(table_frame, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.config(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", lambda _event: self._edit_clip())

        footer = tk.Frame(self.window, bg="#17131f")
        footer.pack(fill=tk.X, padx=20, pady=16)
        ttk.Button(footer, text="Salvar", command=self._save).pack(side=tk.RIGHT, padx=4)
        ttk.Button(footer, text="Fechar", command=self.window.destroy).pack(side=tk.RIGHT, padx=4)
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for clip in sorted(self.timeline.clips.values(), key=lambda item: (item.timeline_start, item.track_id)):
            track = self.timeline.tracks[clip.track_id]
            self.tree.insert("", tk.END, iid=clip.id, text=clip.name, values=(track.name, f"{clip.timeline_start:.3f}", f"{clip.source_in:.3f}", f"{clip.source_out:.3f}", f"{clip.duration:.3f}"))
        self.summary_var.set(f"{len(self.timeline.tracks)} trilhas • {len(self.timeline.clips)} clipes • {self.timeline.duration:.2f} s • {self.timeline.fps:g} fps")
        self._draw_timeline()

    def _draw_timeline(self):
        self.canvas.delete("all")
        width = max(1, self.canvas.winfo_width())
        label_width = 130
        usable = max(1, width - label_width - 20)
        duration = max(1.0, self.timeline.duration)
        track_height = 48
        for index, track in enumerate(self.timeline.tracks.values()):
            y0 = 25 + index * track_height
            self.canvas.create_text(10, y0 + 17, text=track.name, anchor="w", fill="#d8d2df", font=("Segoe UI", 9, "bold"))
            self.canvas.create_line(label_width, y0 + 38, width, y0 + 38, fill="#352a45")
            for clip in self.timeline.clips.values():
                if clip.track_id != track.id:
                    continue
                x0 = label_width + clip.timeline_start * usable / duration
                x1 = label_width + clip.timeline_end * usable / duration
                color = "#7c3aed" if track.kind == "video" else "#0f766e"
                self.canvas.create_rectangle(x0, y0, max(x0 + 3, x1), y0 + 32, fill=color, outline="#d8b4fe", tags=(clip.id,))
                self.canvas.create_text(x0 + 5, y0 + 16, text=clip.name, anchor="w", fill="white", width=max(10, x1 - x0 - 8), tags=(clip.id,))
                self.canvas.tag_bind(clip.id, "<Button-1>", lambda _event, identifier=clip.id: self._select(identifier))
        for second in range(int(duration) + 1):
            x = label_width + second * usable / duration
            self.canvas.create_line(x, 8, x, 18, fill="#756b82")
            self.canvas.create_text(x + 2, 7, text=str(second), anchor="sw", fill="#93889f", font=("Segoe UI", 8))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _select(self, clip_id):
        self.tree.selection_set(clip_id)
        self.tree.focus(clip_id)

    def _add_media(self):
        path = filedialog.askopenfilename(parent=self.window, filetypes=[("Mídia", "*.mp4 *.mov *.mkv *.avi *.wav *.flac *.mp3"), ("Todos os arquivos", "*.*")])
        if path:
            self._create_clip(path)

    def _add_initial_source(self):
        if not self.initial_source:
            messagebox.showinfo("Timeline", "Nenhum vídeo está aberto no editor.", parent=self.window)
            return
        self._create_clip(self.initial_source)

    def _create_clip(self, path):
        media = self.probe_callback(path)
        if isinstance(media, dict):
            duration = max(0.04, float(media.get("duration", 0)))
            has_video = bool(media.get("has_video"))
            has_audio = bool(media.get("has_audio"))
        else:
            duration = max(0.04, float(media))
            has_video, has_audio = True, False
        start = self.timeline.duration
        if has_video:
            tracks = [track for track in self.timeline.tracks.values() if track.kind == "video"]
            track = tracks[0] if tracks else self.timeline.add_track("Vídeo", "video")
            self.timeline.add_clip(track.id, path, 0, duration, start)
        if has_audio and (not has_video or messagebox.askyesno("Áudio da mídia", "Adicionar também o áudio desta mídia à timeline?", parent=self.window)):
            tracks = [track for track in self.timeline.tracks.values() if track.kind == "audio"]
            track = tracks[0] if tracks else self.timeline.add_track("Áudio", "audio")
            self.timeline.add_clip(track.id, path, 0, duration, start)
        if not has_video and not has_audio:
            messagebox.showerror("Timeline", "A mídia não possui stream de vídeo ou áudio reconhecida.", parent=self.window)
            return
        self._changed()

    def _add_track(self):
        kind = simpledialog.askstring("Nova trilha", "Tipo: video ou audio", initialvalue="video", parent=self.window)
        if not kind:
            return
        kind = kind.strip().lower()
        name = simpledialog.askstring("Nova trilha", "Nome da trilha:", initialvalue="Vídeo" if kind == "video" else "Áudio", parent=self.window)
        try:
            self.timeline.add_track(name or kind.title(), kind)
            self._changed()
        except ValueError as error:
            messagebox.showerror("Timeline", str(error), parent=self.window)

    def _selected_clip(self):
        selection = self.tree.selection()
        return self.timeline.clips.get(selection[0]) if selection else None

    def _edit_clip(self):
        clip = self._selected_clip()
        if not clip:
            return
        try:
            start = simpledialog.askfloat("Editar clipe", "Início na timeline:", initialvalue=clip.timeline_start, minvalue=0, parent=self.window)
            source_in = simpledialog.askfloat("Editar clipe", "Entrada na fonte:", initialvalue=clip.source_in, minvalue=0, parent=self.window)
            source_out = simpledialog.askfloat("Editar clipe", "Saída na fonte:", initialvalue=clip.source_out, minvalue=0, parent=self.window)
            current_track = self.timeline.tracks[clip.track_id]
            track_name = simpledialog.askstring("Editar clipe", "Trilha de destino:", initialvalue=current_track.name, parent=self.window)
            if None in {start, source_in, source_out}:
                return
            destination = next((track for track in self.timeline.tracks.values() if track.name == track_name), None)
            if destination is None:
                raise ValueError("A trilha de destino não existe")
            self.timeline.move_clip(clip.id, start, destination.id)
            self.timeline.trim_clip(clip.id, source_in, source_out)
            self._changed()
        except ValueError as error:
            messagebox.showerror("Timeline", str(error), parent=self.window)

    def _split_clip(self):
        clip = self._selected_clip()
        if not clip:
            return
        value = simpledialog.askfloat("Dividir clipe", "Tempo na timeline:", initialvalue=clip.timeline_start + clip.duration / 2, parent=self.window)
        if value is None:
            return
        try:
            self.timeline.split_clip(clip.id, value)
            self._changed()
        except ValueError as error:
            messagebox.showerror("Timeline", str(error), parent=self.window)

    def _add_transition(self):
        selection = self.tree.selection()
        if len(selection) != 2:
            messagebox.showinfo("Transição", "Selecione exatamente dois clipes da mesma trilha.", parent=self.window)
            return
        duration = simpledialog.askfloat("Transição", "Duração do crossfade:", initialvalue=0.5, minvalue=0.01, parent=self.window)
        if duration is None:
            return
        clips = sorted((self.timeline.clips[value] for value in selection), key=lambda item: item.timeline_start)
        try:
            self.timeline.add_transition(clips[0].id, clips[1].id, duration=duration)
            self._changed()
        except ValueError as error:
            messagebox.showerror("Transição", str(error), parent=self.window)

    def _keyframes(self):
        clip = self._selected_clip()
        if clip:
            KeyframeEditorDialog(self.window, self.timeline, clip, self._changed)

    def _remove_clip(self):
        for clip_id in self.tree.selection():
            self.timeline.remove_clip(clip_id)
        self._changed()

    def _save(self):
        self.save_callback(self.timeline)
        self.refresh()

    def _changed(self):
        self.save_callback(self.timeline)
        self.refresh()

    def _render(self):
        if not self.timeline.clips:
            messagebox.showinfo("Timeline", "Adicione ao menos um clipe.", parent=self.window)
            return
        path = filedialog.asksaveasfilename(parent=self.window, defaultextension=".mp4", filetypes=[("Vídeo MP4", "*.mp4")])
        if path:
            self.save_callback(self.timeline)
            self.window.destroy()
            self.render_callback(self.timeline, path)
