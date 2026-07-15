"""
Simple manual mask editor for a single frame restoration.
Controls:
  LMB: paint mask
  RMB: erase mask
  +/-: brush size
  A: apply restoration
  S: save restored
  SPACE: toggle original/restored
  Q/ESC: quit
"""

from typing import Optional
import os
import cv2
import numpy as np
from lib.modules.frame.restoration.restorer import TemporalRestorer, RestorerConfig


def open_manual_editor(
    prev_path: str,
    curr_path: str,
    next_path: str,
    output_path: Optional[str] = None,
    config: Optional[RestorerConfig] = None
):
    restorer = TemporalRestorer(config or RestorerConfig())

    prev = cv2.imread(prev_path, cv2.IMREAD_COLOR)
    curr = cv2.imread(curr_path, cv2.IMREAD_COLOR)
    nxt = cv2.imread(next_path, cv2.IMREAD_COLOR)
    if prev is None or curr is None or nxt is None:
        raise FileNotFoundError("Could not load one or more frames")

    h, w = curr.shape[:2]
    prev = cv2.resize(prev, (w, h), interpolation=cv2.INTER_AREA)
    nxt = cv2.resize(nxt, (w, h), interpolation=cv2.INTER_AREA)

    mask = np.zeros((h, w), dtype=np.uint8)
    restored = curr.copy()
    show_original = False
    brush = 12
    drawing = False
    erasing = False

    win = "Manual Restoration"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    def overlay_mask(img_bgr, mask_u8, alpha=0.35):
        if mask_u8 is None or cv2.countNonZero(mask_u8) == 0:
            return img_bgr
        out = img_bgr.copy()
        m = mask_u8 > 0
        red = np.zeros_like(out)
        red[..., 2] = 255
        out[m] = (out[m] * (1 - alpha) + red[m] * alpha).astype(out.dtype)
        return out

    def render():
        base = curr if show_original else restored
        view = overlay_mask(base, mask, alpha=0.35)
        cv2.putText(view, f"Brush:{brush}  A:apply  S:save  SPACE:orig  Q:quit",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (240, 240, 240), 2, cv2.LINE_AA)
        return view

    def paint_at(x, y, value):
        cv2.circle(mask, (x, y), brush, value, -1)

    def on_mouse(event, x, y, flags, param):
        nonlocal drawing, erasing
        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            paint_at(x, y, 255)
        elif event == cv2.EVENT_MOUSEMOVE and drawing:
            paint_at(x, y, 255)
        elif event == cv2.EVENT_LBUTTONUP:
            drawing = False

        if event == cv2.EVENT_RBUTTONDOWN:
            erasing = True
            paint_at(x, y, 0)
        elif event == cv2.EVENT_MOUSEMOVE and erasing:
            paint_at(x, y, 0)
        elif event == cv2.EVENT_RBUTTONUP:
            erasing = False

    cv2.setMouseCallback(win, on_mouse)

    while True:
        vis = render()
        cv2.imshow(win, vis)
        key = cv2.waitKey(16) & 0xFF

        if key in (27, ord('q'), ord('Q')):
            break
        if key == ord('+') or key == ord('='):
            brush = min(200, brush + 2)
        if key == ord('-') or key == ord('_'):
            brush = max(1, brush - 2)
        if key == 32:
            show_original = not show_original
        if key in (ord('a'), ord('A')):
            restored, _ = restorer.restore_triplet(prev, curr, nxt, mask=mask)
        if key in (ord('s'), ord('S')):
            if output_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                cv2.imwrite(output_path, restored)

    cv2.destroyAllWindows()
