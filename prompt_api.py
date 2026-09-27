"""OneTech Chrome eklentisi için yalnızca loopback üzerinde çalışan küçük HTTP API."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

from prompt_guard import MAX_PROMPT_CHARS, analyze_prompt, get_rules


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/health":
            self._json(200, {"status": "ok", "service": "OneTech local prompt guard"})
        elif self.path == "/api/rules":
            self._json(200, {"rules": get_rules()})
        else:
            self._json(404, {"error": "Bulunamadı"})

    def do_POST(self):
        if self.path != "/api/protect":
            self._json(404, {"error": "Bulunamadı"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_PROMPT_CHARS * 4 + 1024:
            self._json(413, {"error": "İstem çok büyük veya boş."})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            prompt = payload["prompt"]
            if not isinstance(prompt, str):
                raise ValueError("prompt metin olmalı")
            self._json(200, analyze_prompt(prompt))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("OneTech yerel koruma: http://127.0.0.1:8765", flush=True)
    server.serve_forever()
