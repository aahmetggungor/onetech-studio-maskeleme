"""Sentetik dosyalarla temel maskeleme akışını uçtan uca doğrula."""

from pathlib import Path
import tempfile

import cv2
import pymupdf

from core import load_image, mask_regions
from detectors import detect_image
from documents import analyze_pdf, export_redacted_pdf
from video import inspect_video, process_video
from temporal import TemporalMasker


BASE = Path(__file__).parent
EXAMPLES = BASE / "examples"


def verify() -> None:
    image = load_image(EXAMPLES / "ornek_belge.png")
    regions = detect_image(image, faces=False, plates=False, text=True)
    categories = {region.category for region in regions}
    assert {"Ad / soyad", "Telefon", "E-posta", "Adres"} <= categories, categories
    first = regions[0]
    box = (first.x1, first.y1, first.x2, first.y2)
    masked = mask_regions(image, [box], "black")
    assert masked[first.y1:first.y2, first.x1:first.x2].max() == 0
    assert image[first.y1:first.y2, first.x1:first.x2].max() > 0

    scene = load_image(EXAMPLES / "ornek_yuz_plaka.png")
    scene_regions = detect_image(scene, faces=True, plates=True, text=False)
    assert {"Yüz", "Plaka"} <= {region.category for region in scene_regions}

    for name, expected_source in [
        ("ornek_belge.pdf", "PDF metin katmanı"),
        ("ornek_taranmis_belge.pdf", "Taranmış sayfa · OCR"),
    ]:
        pages = analyze_pdf((EXAMPLES / name).read_bytes(), False, False, True, 0.45)
        assert len(pages) == 1 and pages[0].text_source == expected_source
        assert len(pages[0].regions) >= 4
        boxes = [[(r.x1, r.y1, r.x2, r.y2) for r in pages[0].regions]]
        output = export_redacted_pdf(pages, boxes)
        pdf = pymupdf.open(stream=output, filetype="pdf")
        try:
            assert len(pdf) == 1
            assert pdf[0].get_text() == ""
            assert not pdf.metadata.get("author")
        finally:
            pdf.close()

    video_bytes = (EXAMPLES / "ornek_video.mp4").read_bytes()
    info = inspect_video(video_bytes, ".mp4")
    assert info.width == 960 and info.height == 640
    tracker = TemporalMasker()
    initial = detect_image(info.preview, True, True, False)
    assert len(initial) >= 2
    tracker.update(info.preview, initial)
    retained, added = tracker.update(info.preview, [])
    assert added >= 2 and len(retained) >= 2, "Tek karelik algılama boşluğunda maske tutulmalı"
    output, stats = process_video(video_bytes, ".mp4", True, True, 0.45, "black")
    assert output and stats["kare"] > 0 and stats["fps"] <= 8 and stats["algılama"] >= 2
    assert stats["takip"] and stats["maskesiz_kare"] <= stats["kare"]
    assert len(stats["maskesiz_zamanlar"]) == stats["maskesiz_kare"]
    assert all(0 <= moment <= 12 for moment in stats["maskesiz_zamanlar"])
    with tempfile.NamedTemporaryFile(suffix=".mp4") as file:
        file.write(output)
        file.flush()
        capture = cv2.VideoCapture(file.name)
        try:
            ok, frame = capture.read()
            assert ok and frame.shape[:2] == (640, 960)
            for region in detect_image(info.preview, True, True, False):
                cy = (region.y1 + region.y2) // 2
                cx = (region.x1 + region.x2) // 2
                assert frame[cy, cx].max() < 25
        finally:
            capture.release()

    print("OK: yüz+plaka, fotoğraf OCR, PDF metin/OCR, PDF çıktısı ve MP4")


if __name__ == "__main__":
    verify()
