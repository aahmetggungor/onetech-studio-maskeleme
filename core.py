"""İlk maskeleme demosunun görüntü işleme kodu."""

from pathlib import Path
from functools import lru_cache
from threading import Lock

import cv2
import numpy as np
from PIL import Image, ImageOps


MODEL_PATH = Path(__file__).parent / "models" / "face_detection_yunet_2026may.onnx"
MAX_PIXELS = 20_000_000
_FACE_LOCK = Lock()


@lru_cache(maxsize=16)
def _face_detector(width: int, height: int, threshold: float):
    return cv2.FaceDetectorYN.create(
        str(MODEL_PATH), "", (width, height), threshold, 0.3, 5000
    )


def load_image(file) -> np.ndarray:
    """Yüklenen fotoğrafı EXIF yönü düzeltilmiş RGB piksel dizisine çevir."""
    image = ImageOps.exif_transpose(Image.open(file))
    if image.width * image.height > MAX_PIXELS:
        raise ValueError("Fotoğraf çok büyük; en fazla 20 megapiksel yükleyin.")
    return np.asarray(image.convert("RGB")).copy()


def detect_faces(rgb: np.ndarray, threshold: float = 0.6) -> list[tuple[int, int, int, int, float]]:
    """Yüz kutularını (sol, üst, sağ, alt, güven) olarak döndür."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Yüz modeli bulunamadı: {MODEL_PATH}")

    height, width = rgb.shape[:2]
    scale = min(1.0, 1280 / max(width, height))
    detect_width = max(1, round(width * scale))
    detect_height = max(1, round(height * scale))
    detection_image = (
        cv2.resize(rgb, (detect_width, detect_height), interpolation=cv2.INTER_AREA)
        if scale < 1.0
        else rgb
    )
    with _FACE_LOCK:
        detector = _face_detector(detect_width, detect_height, threshold)
        _, detections = detector.detect(cv2.cvtColor(detection_image, cv2.COLOR_RGB2BGR))
    if detections is None:
        return []

    boxes = []
    for face in detections:
        x, y, w, h = face[:4] / scale
        score = float(face[-1])
        # Kutunun kenarına küçük bir pay ekle; yüzün uçları açık kalmasın.
        padding = 0.08
        left = max(0, int(x - w * padding))
        top = max(0, int(y - h * padding))
        right = min(width, int(x + w * (1 + padding)))
        bottom = min(height, int(y + h * (1 + padding)))
        if right > left and bottom > top:
            boxes.append((left, top, right, bottom, score))
    return boxes


def mask_regions(
    rgb: np.ndarray,
    boxes: list[tuple[int, int, int, int]],
    method: str = "black",
) -> np.ndarray:
    """Seçili dikdörtgenlere maske uygula; özgün görüntüyü değiştirme."""
    result = rgb.copy()
    height, width = result.shape[:2]
    for x1, y1, x2, y2 in boxes:
        x1, x2 = sorted((max(0, min(width, int(x1))), max(0, min(width, int(x2)))))
        y1, y2 = sorted((max(0, min(height, int(y1))), max(0, min(height, int(y2)))))
        if x2 <= x1 or y2 <= y1:
            continue
        roi = result[y1:y2, x1:x2]
        if method == "black":
            roi[:] = 0
        elif method == "blur":
            # Harita benzeri yumuşak ama yoğun bulanıklık: önce ayrıntıyı düşük
            # çözünürlükte yok et, ardından geniş Gauss filtresi uygula.
            h, w = roi.shape[:2]
            small = cv2.resize(roi, (max(1, w // 12), max(1, h // 12)), interpolation=cv2.INTER_AREA)
            softened = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
            sigma = max(7.0, min(w, h) * 0.18)
            roi[:] = cv2.GaussianBlur(softened, (0, 0), sigmaX=sigma, sigmaY=sigma)
        elif method == "pixel":
            small = cv2.resize(roi, (max(1, roi.shape[1] // 16), max(1, roi.shape[0] // 16)))
            roi[:] = cv2.resize(small, (roi.shape[1], roi.shape[0]), interpolation=cv2.INTER_NEAREST)
        else:
            raise ValueError(f"Bilinmeyen maskeleme yöntemi: {method}")
    return result


def preview_boxes(rgb: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    """Onaylanan kutuları önizleme üzerinde göster."""
    result = rgb.copy()
    for x1, y1, x2, y2 in boxes:
        cv2.rectangle(result, (x1, y1), (x2, y2), (0, 220, 90), 3)
    return result
