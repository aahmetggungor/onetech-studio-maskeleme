"""Yerel yüz, plaka ve OCR tabanlı hassas alan tespiti."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

import cv2
import numpy as np

from core import detect_faces


BASE = Path(__file__).parent
PLATE_MODEL = BASE / "models/plate_v9/yolo-v9-t-384-license-plates-end2end.onnx"
OCR_MODEL = BASE / "models/ocr/latin_rec.onnx"


@dataclass(frozen=True)
class Region:
    category: str
    source: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    def row(self) -> dict:
        return {"Kapat": True, "Tür": self.category, "Kaynak": self.source,
                "Güven": round(self.confidence, 2), "x1": self.x1, "y1": self.y1,
                "x2": self.x2, "y2": self.y2}


def _region(category: str, source: str, confidence: float, box, width: int, height: int,
            pad: float = 0.04) -> Region | None:
    x1, y1, x2, y2 = map(float, box)
    dx, dy = (x2 - x1) * pad, (y2 - y1) * pad
    x1, y1 = max(0, int(x1 - dx)), max(0, int(y1 - dy))
    x2, y2 = min(width, int(x2 + dx + 1)), min(height, int(y2 + dy + 1))
    if x2 <= x1 or y2 <= y1:
        return None
    return Region(category, source, confidence, x1, y1, x2, y2)


@lru_cache(maxsize=1)
def _plate_detector():
    from open_image_models import create_detector

    return create_detector(str(PLATE_MODEL), backend="yolo_v9",
                           class_labels=["License Plate"], conf_thresh=0.25)


def detect_plates(rgb: np.ndarray, threshold: float = 0.3) -> list[Region]:
    height, width = rgb.shape[:2]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    detections = _plate_detector().predict(bgr)
    regions = []
    for detection in detections:
        if detection.confidence < threshold:
            continue
        b = detection.bounding_box
        region = _region("Plaka", "AI · YOLOv9", float(detection.confidence),
                         (b.x1, b.y1, b.x2, b.y2), width, height, 0.09)
        if region:
            regions.append(region)
    return regions


@lru_cache(maxsize=1)
def _ocr_engine():
    from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

    return RapidOCR(params={
        "Rec.lang_type": LangRec.LATIN,
        "Rec.ocr_version": OCRVersion.PPOCRV5,
        "Rec.model_type": ModelType.MOBILE,
        "Rec.model_path": str(OCR_MODEL),
    })


def ocr_lines(rgb: np.ndarray) -> list[tuple[str, tuple[int, int, int, int], float]]:
    output = _ocr_engine()(rgb)
    if output.boxes is None or output.txts is None:
        return []
    lines = []
    for points, text, score in zip(output.boxes, output.txts, output.scores):
        points = np.asarray(points)
        box = (int(points[:, 0].min()), int(points[:, 1].min()),
               int(points[:, 0].max()), int(points[:, 1].max()))
        lines.append((text, box, float(score)))
    return lines


EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE = re.compile(r"(?<!\d)(?:\+?90\s*|0\s*)?5\d{2}[\s().-]*\d{3}[\s().-]*\d{2}[\s().-]*\d{2}(?!\d)")
TCKN = re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")
IBAN = re.compile(r"\bTR[\s-]?(?:\d[\s-]?){24}\b", re.I)
KEYWORDS = {
    "Ad / soyad": re.compile(r"\b(?:ad\s*soyad|adı\s*soyadı|isim\s*soyisim)\b", re.I),
    "Adres": re.compile(r"\b(?:adres|ikametg[aâ]h)\b", re.I),
    "Kimlik / belge numarası": re.compile(r"(?:T\.?\s*C\.?\s*kimlik|kimlik\s*no|belge\s*no|pasaport\s*no|seri\s*no)", re.I),
}


def _valid_tckn(value: str) -> bool:
    digits = list(map(int, value))
    return (len(digits) == 11 and digits[0] != 0
            and ((sum(digits[:9:2]) * 7 - sum(digits[1:8:2])) % 10 == digits[9])
            and sum(digits[:10]) % 10 == digits[10])


def sensitive_categories(text: str) -> list[str]:
    categories = []
    if EMAIL.search(text):
        categories.append("E-posta")
    if PHONE.search(text):
        categories.append("Telefon")
    if any(_valid_tckn(m.group()) for m in TCKN.finditer(text)):
        categories.append("T.C. kimlik no")
    if IBAN.search(text):
        categories.append("IBAN")
    for category, pattern in KEYWORDS.items():
        if pattern.search(text):
            categories.append(category)
    return categories


def text_regions(lines: list[tuple[str, tuple[int, int, int, int], float]],
                 width: int, height: int, source: str) -> list[Region]:
    regions = []
    for text, box, score in lines:
        categories = sensitive_categories(text)
        if not categories:
            continue
        region = _region(" / ".join(categories), source, score, box, width, height, 0.07)
        if region:
            regions.append(region)
    return regions


def detect_image(rgb: np.ndarray, faces: bool = True, plates: bool = True,
                 text: bool = True, threshold: float = 0.45) -> list[Region]:
    height, width = rgb.shape[:2]
    regions = []
    if faces:
        for x1, y1, x2, y2, score in detect_faces(rgb, threshold):
            regions.append(Region("Yüz", "AI · YuNet", score, x1, y1, x2, y2))
    if plates:
        regions.extend(detect_plates(rgb, max(0.25, threshold - 0.1)))
    if text:
        regions.extend(text_regions(ocr_lines(rgb), width, height, "OCR + kural"))
    return regions
