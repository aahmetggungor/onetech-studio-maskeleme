"""Kısa videoları yerelde örnekleyip yüz/plaka maskeleyen demo akışı."""

from dataclasses import dataclass
import math
from pathlib import Path
import subprocess
import tempfile
import time

import cv2
import imageio_ffmpeg
import numpy as np

from core import mask_regions
from detectors import detect_image
from temporal import TemporalMasker


MAX_SECONDS = 12
MAX_FRAMES = 120


@dataclass(frozen=True)
class VideoInfo:
    preview: np.ndarray
    fps: float
    width: int
    height: int
    duration: float


def _input_file(data: bytes, suffix: str) -> Path:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as file:
        file.write(data)
        return Path(file.name)


def inspect_video(data: bytes, suffix: str) -> VideoInfo:
    path = _input_file(data, suffix)
    try:
        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                raise ValueError("Video açılamadı. MP4/MOV dosyasını kontrol edin.")
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            if fps <= 0 or fps > 240:
                fps = 25.0
            total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            ok, frame = capture.read()
            if not ok:
                raise ValueError("Videodan ilk kare okunamadı.")
            height, width = frame.shape[:2]
            if width * height > 4_000_000:
                raise ValueError("Video çözünürlüğü çok büyük; en fazla 4 MP yükleyin.")
            return VideoInfo(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), fps, width, height,
                             total / fps if total > 0 else 0.0)
        finally:
            capture.release()
    finally:
        path.unlink(missing_ok=True)


def process_video(data: bytes, suffix: str, faces: bool, plates: bool,
                  threshold: float, method: str,
                  manual_box: tuple[int, int, int, int] | None = None,
                  temporal: bool = True) -> tuple[bytes, dict]:
    source = _input_file(data, suffix)
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        output = Path(tmp.name)
    started = time.perf_counter()
    try:
        capture = cv2.VideoCapture(str(source))
        if not capture.isOpened():
            raise ValueError("Video açılamadı.")
        try:
            fps = float(capture.get(cv2.CAP_PROP_FPS)) or 25.0
            if fps <= 0 or fps > 240:
                fps = 25.0
            step = max(1, math.ceil(fps / 8))
            output_fps = fps / step
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if width <= 0 or height <= 0 or width * height > 4_000_000:
                raise ValueError("Video boyutu desteklenmiyor.")
            scale = min(1.0, 960 / width)
            out_width = max(2, round(width * scale) // 2 * 2)
            out_height = max(2, round(height * scale) // 2 * 2)
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{out_width}x{out_height}",
                   "-r", f"{output_fps:.5f}", "-i", "-", "-an", "-c:v", "libx264",
                   "-preset", "veryfast", "-crf", "25", "-pix_fmt", "yuv420p",
                   "-movflags", "+faststart", str(output)]
            encoder = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.PIPE)
            frame_no = processed = detected = tracked_only = no_mask_frames = 0
            no_mask_times: list[float] = []
            masker = TemporalMasker() if temporal and (faces or plates) else None
            try:
                while frame_no < int(MAX_SECONDS * fps) and processed < MAX_FRAMES:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    if frame_no % step == 0:
                        frame = cv2.resize(frame, (out_width, out_height), interpolation=cv2.INTER_AREA)
                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        regions = detect_image(rgb, faces, plates, False, threshold)
                        if masker is None:
                            boxes = [(r.x1, r.y1, r.x2, r.y2) for r in regions]
                        else:
                            boxes, extra = masker.update(rgb, regions)
                            tracked_only += extra
                        if manual_box:
                            boxes.append(tuple(round(v * out_width / width) if i % 2 == 0
                                               else round(v * out_height / height)
                                               for i, v in enumerate(manual_box)))
                        masked = mask_regions(rgb, boxes, method)
                        if not boxes:
                            no_mask_frames += 1
                            no_mask_times.append(round(frame_no / fps, 2))
                        try:
                            encoder.stdin.write(masked.tobytes())
                        except BrokenPipeError as error:
                            raise RuntimeError("Video kodlayıcı kapandı.") from error
                        detected += len(regions)
                        processed += 1
                    frame_no += 1
            finally:
                encoder.stdin.close()
            error_text = encoder.stderr.read().decode("utf-8", "replace")
            if encoder.wait() != 0 or processed == 0:
                raise RuntimeError(f"Video üretilemedi: {error_text[-300:]}")
            stats = {"kare": processed, "süre": round(time.perf_counter() - started, 2),
                     "algılama": detected, "takiple_eklenen": tracked_only,
                     "maskesiz_kare": no_mask_frames, "maskesiz_zamanlar": no_mask_times,
                     "takip": bool(masker),
                     "fps": round(output_fps, 1)}
            return output.read_bytes(), stats
        finally:
            capture.release()
    finally:
        source.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
