"""Tamamı uydurma bilgiler içeren sunum dosyaları üretir."""

from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).parent
FONT = Path("C:/Windows/Fonts/arial.ttf")
BOLD = Path("C:/Windows/Fonts/arialbd.ttf")


def font(size: int, bold: bool = False):
    path = BOLD if bold else FONT
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def document_image() -> Image.Image:
    image = Image.new("RGB", (1280, 820), "#f5f7fb")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((55, 45, 1225, 775), radius=30, fill="white", outline="#bdcad8", width=3)
    draw.rectangle((55, 45, 1225, 155), fill="#17375b")
    draw.text((90, 75), "ÖRNEK BAŞVURU BELGESİ", fill="white", font=font(39, True))
    rows = [
        "Ad Soyad: Örnek Öğrenci",
        "T.C. Kimlik No: 12345678901",
        "Telefon: 0555 000 00 00",
        "E-posta: ornek@example.invalid",
        "Adres: Örnek Mahallesi 1. Sokak No: 2",
        "Belge No: DEMO-2026-001",
    ]
    for index, row in enumerate(rows):
        draw.text((100, 205 + index * 82), row, fill="#172333", font=font(34))
    draw.text((100, 720), "SADECE SENTETİK DEMO VERİSİDİR", fill="#bd4050", font=font(27, True))
    return image


def native_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    if FONT.exists():
        page.insert_font(fontname="ArialDemo", fontfile=str(FONT))
        fontname = "ArialDemo"
    else:
        fontname = "helv"
    lines = [
        "ÖRNEK BAŞVURU BELGESİ — GERÇEK VERİ DEĞİL",
        "Ad Soyad: Örnek Öğrenci",
        "T.C. Kimlik No: 12345678901",
        "Telefon: 0555 000 00 00",
        "E-posta: ornek@example.invalid",
        "Adres: Örnek Mahallesi 1. Sokak No: 2",
        "Belge No: DEMO-2026-001",
    ]
    for index, line in enumerate(lines):
        page.insert_text((55, 90 + index * 70), line, fontsize=18,
                         fontname=fontname, color=(0.1, 0.2, 0.3))
    result = doc.tobytes()
    doc.close()
    return result


def scanned_pdf(image: Image.Image) -> bytes:
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    doc = pymupdf.open()
    page = doc.new_page(width=640, height=410)
    page.insert_image(page.rect, stream=image_bytes.getvalue())
    result = doc.tobytes()
    doc.close()
    return result


def demo_video() -> None:
    path = HERE / "ornek_video.mp4"
    photo_path = HERE / "ornek_yuz_plaka.png"
    if photo_path.exists():
        source = cv2.imread(str(photo_path))
        source = cv2.resize(source, (1000, 667), interpolation=cv2.INTER_AREA)
        size = (960, 640)
    else:
        source = None
        size = (640, 360)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, size)
    if not writer.isOpened():
        raise RuntimeError("Örnek video üretilemedi.")
    try:
        for index in range(25):
            if source is not None:
                offset = round(index * 40 / 24)
                frame = source[13:653, offset:offset + 960].copy()
            else:
                frame = np.full((360, 640, 3), (236, 232, 224), dtype=np.uint8)
                x = 60 + index * 5
                cv2.rectangle(frame, (x, 145), (x + 230, 265), (93, 59, 34), -1)
                cv2.rectangle(frame, (x + 70, 215), (x + 175, 250), (245, 245, 245), -1)
                cv2.putText(frame, "DEMO 2026", (x + 77, 238), cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, (20, 20, 20), 2)
            writer.write(frame)
    finally:
        writer.release()


if __name__ == "__main__":
    image = document_image()
    image.save(HERE / "ornek_belge.png")
    (HERE / "ornek_belge.pdf").write_bytes(native_pdf())
    (HERE / "ornek_taranmis_belge.pdf").write_bytes(scanned_pdf(image))
    demo_video()
    print("Sentetik demo dosyaları üretildi:", HERE)
