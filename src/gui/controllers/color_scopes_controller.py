"""Current-frame color scope integration."""

import cv2
from tkinter import messagebox

from gui.dialogs.color_scopes_dialog import ColorScopesDialog


class ColorScopesController:
    def __init__(self, editor):
        self.editor = editor

    def open_dialog(self):
        if self._current_frame() is None:
            messagebox.showinfo("Scopes", "Extraia ou carregue um frame primeiro.")
            return
        ColorScopesDialog(self.editor.root, self._current_frame)

    def _current_frame(self):
        manager = self.editor.frame_manager
        if not manager or not manager.frames:
            return None
        path = self.editor._get_source_frame_path(manager.current_frame_index)
        return cv2.imread(path, cv2.IMREAD_COLOR) if path else None
