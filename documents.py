"""PDF sayfalarını analiz eder ve yalnızca maskelenmiş piksellerden yeni PDF kurar."""

from dataclasses import dataclass
from io import BytesIO

import numpy as np
import pymupdf
from PIL import Image

from core import mask_regions
from detectors import Region, detect_image, ocr_lines, text_regions


MAX_PAGES = 8
MAX_PAGE_PIXELS = 12_000_000
ZOOM = 1.7


@dataclass
class PageData:
    image: np.ndarray
    regions: list[Region]
    page_width: float
    page_height: float
    text_source: str


def _pdf_text_lines(page, zoom: float) -> list[tuple[str, tuple[int, int, int, int], float]]:
    lines = []
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        if "lines" not in block:
            continue
        for line in block["lines"]:
            spans = [span for span in line["spans"] if span["text"].strip()]
            if not spans:
                continue
            text = " ".join(span["text"] for span in spans)
            rect = pymupdf.Rect(
                min(span["bbox"][0] for span in spans),
                min(span["bbox"][1] for span in spans),
                max(span["bbox"][2] for span in spans),
                max(span["bbox"][3] for span in spans),
            ) * page.rotation_matrix
            lines.append((text, tuple(round(v * zoom) for v in rect), 1.0))
    return lines


def analyze_pdf(data: bytes, faces: bool, plates: bool, text: bool,
                threshold: float) -> list[PageData]:
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as error:
        raise ValueError("PDF açılamadı; dosyayı kontrol edin.") from error
    try:
        if document.needs_pass:
            raise ValueError("Parolalı PDF bu demoda desteklenmiyor.")
        if len(document) == 0 or len(document) > MAX_PAGES:
            raise ValueError(f"PDF 1–{MAX_PAGES} sayfa içermeli.")
        pages = []
        for page in document:
            if page.rect.width * page.rect.height * ZOOM * ZOOM > MAX_PAGE_PIXELS:
                raise ValueError("PDF sayfası çok büyük; daha küçük bir dosya yükleyin.")
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), alpha=False)
            image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                pixmap.height, pixmap.width, pixmap.n).copy()
            if pixmap.n != 3:
                image = image[:, :, :3]
            height, width = image.shape[:2]
            regions = detect_image(image, faces, plates, False, threshold)
            source = "Kapalı"
            if text:
                lines = _pdf_text_lines(page, ZOOM)
                if lines:
                    source = "PDF metin katmanı"
                    regions.extend(text_regions(lines, width, height, source))
                else:
                    source = "Taranmış sayfa · OCR"
                    regions.extend(text_regions(ocr_lines(image), width, height, source))
            pages.append(PageData(image, regions, page.rect.width, page.rect.height, source))
        return pages
    finally:
        document.close()


def export_redacted_pdf(pages: list[PageData], boxes_per_page: list[list[tuple[int, int, int, int]]]) -> bytes:
    """Kaynak PDF nesnelerini kopyalamadan güvenli, görüntü tabanlı PDF üret."""
    output = pymupdf.open()
    try:
        for page, boxes in zip(pages, boxes_per_page, strict=True):
            masked = mask_regions(page.image, boxes, "black")
            image_data = BytesIO()
            Image.fromarray(masked).save(image_data, format="PNG")
            new_page = output.new_page(width=page.page_width, height=page.page_height)
            new_page.insert_image(new_page.rect, stream=image_data.getvalue())
        output.set_metadata({})
        return output.tobytes(garbage=4, deflate=True)
    finally:
        output.close()
