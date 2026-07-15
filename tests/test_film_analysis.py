import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.damage_analysis import FrameDamageAnalyzer
from core.film_analysis import FilmPerforationDetector


def film_frame(shift_x=0, shift_y=0, holes=5):
    image = np.full((240, 320, 3), 24, dtype=np.uint8)
    image[:, 42:278] = (80, 100, 125)
    for index in range(holes):
        y = 14 + index * 43
        cv2.rectangle(image, (10, y), (26, y + 23), (245, 245, 245), -1)
        cv2.rectangle(image, (294, y), (310, y + 23), (245, 245, 245), -1)
    if shift_x or shift_y:
        matrix = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
        image = cv2.warpAffine(image, matrix, (320, 240), borderValue=(24, 24, 24))
    return image


def test_detects_perforations_on_both_film_edges():
    result = FilmPerforationDetector().detect(film_frame())

    assert result.left_count == 5
    assert result.right_count == 5
    assert result.confidence > 0.7


def test_estimates_translation_needed_to_register_shifted_film():
    detector = FilmPerforationDetector()
    registration = detector.estimate_registration(
        film_frame(), film_frame(shift_x=3, shift_y=-4)
    )

    assert registration.matches >= 8
    assert abs(registration.dx + 3) <= 0.5
    assert abs(registration.dy - 4) <= 0.5
    assert registration.confidence > 0.5


def test_damage_analysis_reports_perforation_count_and_shift():
    analyzer = FrameDamageAnalyzer()
    result = analyzer.analyze(film_frame(shift_x=7), previous=film_frame())

    assert result.perforation_count >= 8
    assert result.possible_perforation_damage
    assert result.status == "perforation"
