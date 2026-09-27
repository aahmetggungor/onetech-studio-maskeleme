"""Video tutarlılığı için ViTTrack modelini doğrulanmış kaynaktan indir."""

from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen


MODEL = Path(__file__).resolve().parent / "models" / "vittrack.onnx"
EXPECTED = "2990f0b7cd44d92afa48cd97db6de7be113fc1d9594fddb74e2725c10478e91d"
URL = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/object_tracking_vittrack/object_tracking_vittrack_2023sep.onnx"


def valid() -> bool:
    return MODEL.is_file() and sha256(MODEL.read_bytes()).hexdigest() == EXPECTED


if __name__ == "__main__":
    if valid():
        print("ViTTrack modeli doğrulandı.")
    else:
        MODEL.parent.mkdir(exist_ok=True)
        temporary = MODEL.with_suffix(".download")
        with urlopen(URL, timeout=120) as source, temporary.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
        if sha256(temporary.read_bytes()).hexdigest() != EXPECTED:
            temporary.unlink(missing_ok=True)
            raise ValueError("ViTTrack indirmesi hash doğrulamasını geçmedi.")
        temporary.replace(MODEL)
        print("ViTTrack indirildi ve doğrulandı.")
