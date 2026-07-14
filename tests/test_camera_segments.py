import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.camera_segments import CameraSegment, CameraSegmentStore, detect_camera_segments


def test_camera_segment_store_round_trip(tmp_path):
    store = CameraSegmentStore(tmp_path)
    segment = CameraSegment.create("Plano geral", 20, 45)

    store.add("rolo.mov", segment)

    assert store.list("rolo.mov") == [segment]
    assert store.list("outra-fonte.mov") == []
    assert (tmp_path / "metadata" / "camera_segments.json").is_file()


def test_detect_camera_segments_finds_strong_cut(tmp_path):
    frame_paths = []
    for index in range(28):
        image = np.zeros((90, 160, 3), dtype=np.uint8)
        if index < 14:
            image[:, :80] = (20, 40, 180)
            cv2.circle(image, (35, 45), 20, (240, 220, 40), -1)
        else:
            image[:, 80:] = (170, 35, 20)
            cv2.rectangle(image, (100, 20), (150, 75), (30, 230, 210), -1)
        path = tmp_path / f"frame_{index:04d}.png"
        assert cv2.imwrite(str(path), image)
        frame_paths.append(str(path))

    segments = detect_camera_segments(frame_paths, threshold=0.18, minimum_length=5)

    assert [(item.start, item.end) for item in segments] == [(0, 13), (14, 27)]

