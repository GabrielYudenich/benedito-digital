import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.clean_plate import (
    apply_clean_plate,
    build_clean_plate,
    compose_plate_layer,
    detect_transient_defects,
    make_transparent_plate,
    restrict_defect_mask,
)
from gui.dialogs.clean_plate_manager_dialog import CleanPlateEditorDialog


def _background():
    height, width = 120, 180
    x = np.linspace(25, 145, width, dtype=np.uint8)
    y = np.linspace(0, 45, height, dtype=np.uint8)[:, None]
    gray = np.clip(x[None, :] + y, 0, 255).astype(np.uint8)
    image = cv2.merge((gray, np.roll(gray, 11, axis=1), np.roll(gray, 23, axis=1)))
    cv2.line(image, (0, 24), (179, 24), (210, 190, 160), 2)
    return image


def test_clean_plate_repairs_dust_without_replacing_moving_subject():
    background = _background()
    frames = []
    for index in range(9):
        frame = background.copy()
        left = 30 + index * 8
        cv2.rectangle(frame, (left, 47), (left + 28, 105), (18, 18, 225), -1)
        frames.append(frame)
    dust_center = (150, 80)
    cv2.circle(frames[4], dust_center, 2, (255, 255, 255), -1)

    plate, static_mask, diagnostics = build_clean_plate(frames)
    defect_mask = detect_transient_defects(frames[3], frames[4], frames[5])
    restored, apply_diagnostics = apply_clean_plate(
        frames[4], plate, static_mask, defect_mask
    )

    x, y = dust_center
    before_error = np.mean(np.abs(frames[4][y - 2 : y + 3, x - 2 : x + 3].astype(float) - background[y - 2 : y + 3, x - 2 : x + 3]))
    after_error = np.mean(np.abs(restored[y - 2 : y + 3, x - 2 : x + 3].astype(float) - background[y - 2 : y + 3, x - 2 : x + 3]))
    subject = (slice(47, 106), slice(62, 91))

    assert diagnostics["camera_static"] is True
    assert apply_diagnostics["replaced_pixels"] > 0
    assert after_error < before_error
    assert np.max(cv2.absdiff(restored[subject], frames[4][subject])) <= 2


def test_clean_plate_requires_at_least_three_frames():
    frame = _background()

    try:
        build_clean_plate([frame, frame])
    except ValueError as error:
        assert "three frames" in str(error)
    else:
        raise AssertionError("Expected a ValueError")


def test_shared_plate_region_is_reused_instead_of_per_frame_selection():
    defects = np.full((20, 30), 255, dtype=np.uint8)
    frame_selection = np.zeros_like(defects)
    frame_selection[:, :10] = 255
    shared_region = np.zeros_like(defects)
    shared_region[:, 20:] = 255

    restricted = restrict_defect_mask(
        defects,
        frame_selection=frame_selection,
        application_region=shared_region,
    )

    assert np.count_nonzero(restricted[:, :10]) == 0
    assert np.all(restricted[:, 20:] == 255)


def test_selected_base_keeps_more_detail_than_temporal_median():
    sharp = _background()
    cv2.putText(
        sharp,
        "FUNDO",
        (15, 72),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (240, 240, 240),
        2,
        cv2.LINE_AA,
    )
    frames = [cv2.GaussianBlur(sharp, (0, 0), 1.7) for _ in range(7)]
    frames.insert(0, sharp.copy())

    plate, _static_mask, diagnostics = build_clean_plate(
        frames,
        base_frame=sharp,
        base_strategy="selected",
    )

    assert diagnostics["base_strategy"] == "selected"
    assert diagnostics["plate_sharpness"] > diagnostics["median_sharpness"] * 1.35
    assert np.mean(cv2.absdiff(plate, sharp)) < 8


def test_background_application_replaces_static_area_but_protects_subject():
    plate = _background()
    current = cv2.GaussianBlur(plate, (0, 0), 1.4)
    current = np.clip(current.astype(np.int16) - 16, 0, 255).astype(np.uint8)
    cv2.rectangle(current, (58, 42), (118, 112), (20, 20, 235), -1)
    static_mask = np.full(current.shape[:2], 255, dtype=np.uint8)
    whole_background = np.full(current.shape[:2], 255, dtype=np.uint8)

    restored, diagnostics = apply_clean_plate(
        current,
        plate,
        static_mask,
        whole_background,
        application_mode="background",
    )

    assert diagnostics["application_mode"] == "background"
    assert diagnostics["dynamic_foreground_pixels"] > 0
    assert diagnostics["replaced_pixels"] > current.shape[0] * current.shape[1] * 0.45
    current_detail = cv2.Laplacian(current[:35], cv2.CV_64F).var()
    restored_detail = cv2.Laplacian(restored[:35], cv2.CV_64F).var()
    assert restored_detail > current_detail * 1.2
    assert abs(float(restored[:35].mean()) - float(current[:35].mean())) < 3
    assert np.max(cv2.absdiff(restored[52:102, 68:108], current[52:102, 68:108])) <= 5


def test_transparent_plate_uses_static_mask_as_alpha():
    plate = _background()
    static_mask = np.full(plate.shape[:2], 255, dtype=np.uint8)
    static_mask[30:90, 50:130] = 0

    transparent = make_transparent_plate(plate, static_mask)

    assert transparent.shape[2] == 4
    assert np.array_equal(transparent[..., :3], plate)
    assert np.all(transparent[40:80, 60:120, 3] == 0)
    assert np.all(transparent[:20, :, 3] == 255)


def test_reveal_mask_restores_source_without_flattening_layer():
    source = np.full((60, 90, 3), 40, dtype=np.uint8)
    composite = np.full_like(source, 180)
    reveal = np.zeros(source.shape[:2], dtype=np.uint8)
    reveal[15:45, 25:65] = 255

    corrected = compose_plate_layer(source, composite, reveal, feather=1.0)

    assert np.all(corrected[25:35, 35:55] == 40)
    assert np.all(corrected[:8, :8] == 180)
    assert np.all(composite == 180)


def test_plate_editor_transparency_participates_in_undo_and_redo():
    dialog = object.__new__(CleanPlateEditorDialog)
    dialog.image = np.full((50, 70, 3), 120, dtype=np.uint8)
    dialog.noise_mask = np.zeros((50, 70), dtype=np.uint8)
    dialog.static_mask = np.full((50, 70), 255, dtype=np.uint8)
    dialog.undo_stack = []
    dialog.redo_stack = []
    dialog.brush_size = type("Brush", (), {"get": lambda self: 6})()
    dialog.tool = "transparent"
    dialog.last_point = (20, 25)
    dialog._schedule_redraw = lambda: None

    dialog._push_undo()
    dialog._apply_point((28, 25))

    assert dialog.static_mask[25, 24] == 0
    dialog._undo()
    assert np.all(dialog.static_mask == 255)
    dialog._redo()
    assert dialog.static_mask[25, 24] == 0
