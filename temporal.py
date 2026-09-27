"""Yüz/plaka algılaması bir karede kaçırırsa kısa süreli takip kutusu kullan."""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from detectors import Region


MODEL = Path(__file__).resolve().parent / "models" / "vittrack.onnx"
MAX_MISSED = 2


def _overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def _box(region: Region) -> tuple[int, int, int, int]:
    return region.x1, region.y1, region.x2, region.y2


def _new_tracker(bgr: np.ndarray, box: tuple[int, int, int, int]):
    if not MODEL.is_file():
        raise FileNotFoundError("Video takip modeli eksik: models/vittrack.onnx")
    params = cv2.TrackerVit_Params()
    params.net = str(MODEL)
    params.backend = cv2.dnn.DNN_BACKEND_OPENCV
    params.target = cv2.dnn.DNN_TARGET_CPU
    tracker = cv2.TrackerVit_create(params)
    x1, y1, x2, y2 = box
    tracker.init(bgr, (x1, y1, x2 - x1, y2 - y1))
    return tracker


@dataclass
class Track:
    category: str
    box: tuple[int, int, int, int]
    model: object
    missed: int = 0


class TemporalMasker:
    def __init__(self):
        self.tracks: list[Track] = []

    def update(self, rgb: np.ndarray, detections: list[Region]) -> tuple[list[tuple[int, int, int, int]], int]:
        """Detektör kutuları öncelikli; yalnızca kaçırılan bölgeler için takip ekle."""
        height, width = rgb.shape[:2]
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        for track in self.tracks:
            try:
                found, xywh = track.model.update(bgr)
                if found and track.model.getTrackingScore() >= .2:
                    x, y, w, h = xywh
                    track.box = (max(0, x), max(0, y), min(width, x + w), min(height, y + h))
            except cv2.error:
                pass

        used: set[int] = set()
        next_tracks: list[Track] = []
        boxes: list[tuple[int, int, int, int]] = []
        for region in detections:
            actual = _box(region)
            boxes.append(actual)
            best_index = None
            best_overlap = .15
            for index, track in enumerate(self.tracks):
                if index not in used and track.category == region.category:
                    overlap = _overlap(actual, track.box)
                    if overlap > best_overlap:
                        best_overlap, best_index = overlap, index
            if best_index is not None:
                used.add(best_index)
            try:
                next_tracks.append(Track(region.category, actual, _new_tracker(bgr, actual)))
            except cv2.error:
                continue

        tracked_only = 0
        for index, track in enumerate(self.tracks):
            if index in used:
                continue
            track.missed += 1
            if track.missed <= MAX_MISSED and track.box[2] > track.box[0] and track.box[3] > track.box[1]:
                boxes.append(track.box)
                next_tracks.append(track)
                tracked_only += 1
        self.tracks = next_tracks
        return boxes, tracked_only
