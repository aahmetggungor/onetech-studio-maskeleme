"""Ortak prompt motoru, yerel API ve varsayılan blur için küçük doğrulama."""

from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import Request, urlopen
import json

import numpy as np
import cv2

from core import mask_regions
from prompt_api import Handler
from prompt_guard import analyze_prompt, mask_prompt


prompt = ("ayse@example.com, ayse@example.com ve 0532 123 45 67; "
          "TCKN 10000000146; IBAN TR330006100519786457841326; "
          "kart 4111 1111 1111 1111; şirket kodu MAVI-42")
result = analyze_prompt(prompt, rules=["MAVI-42"])
labels = [item["type"] for item in result["matches"]]
assert labels.count("E-posta") == 2, labels
assert {"Telefon", "T.C. kimlik", "IBAN", "Kart numarası", "Özel kural"}.issubset(labels), labels
protected = mask_prompt(prompt, result["matches"])
assert "ayse@example.com" not in protected and "10000000146" not in protected
assert protected.count("[E-POSTA]") == 2
partly = mask_prompt(prompt, result["matches"], [False] + [True] * (len(labels) - 1))
assert partly.count("ayse@example.com") == 1
assert not analyze_prompt("rastgele 12345678901 ve 4111 1111 1111 1112", rules=[])["matches"]

server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    url = f"http://127.0.0.1:{server.server_port}"
    with urlopen(f"{url}/api/health") as response:
        assert json.load(response)["status"] == "ok"
    request = Request(f"{url}/api/protect", data=json.dumps({"prompt": prompt}).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request) as response:
        assert len(json.load(response)["matches"]) >= 6
finally:
    server.shutdown()
    server.server_close()

image = np.indices((120, 220)).sum(axis=0) % 2 * 255
image = np.stack((image, image, image), axis=-1).astype(np.uint8)
blurred = mask_regions(image, [(10, 10, 210, 110)], "blur")
assert blurred[30:90, 30:190].mean() > 20
assert cv2.Laplacian(blurred[30:90, 30:190], cv2.CV_64F).var() < 0.05 * cv2.Laplacian(
    image[30:90, 30:190], cv2.CV_64F).var()
print("OK: ortak prompt kuralları, kısmi maske, yerel API ve yoğun blur")
