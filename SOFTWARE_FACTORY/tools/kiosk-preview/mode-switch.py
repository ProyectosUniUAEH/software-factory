#!/usr/bin/env python3
"""API local mínima para cambiar kiosk ↔ consola (solo 127.0.0.1)."""
from __future__ import annotations

import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "127.0.0.1"
PORT = 8889
RETURN_CMD = "sudo kaanbal-ui"
CONSOLE_BIN = "/usr/local/bin/kaanbal-console"


class ModeHandler(BaseHTTPRequestHandler):
    server_version = "KaanbalModeSwitch/0.1"

    def log_message(self, fmt: str, *args) -> None:
        return

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8888")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/api/health":
            self._json(
                200,
                {
                    "ok": True,
                    "mode": "kiosk",
                    "return_command": RETURN_CMD,
                    "hint": "Use este comando en consola para volver a la interfaz.",
                },
            )
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/api/console":
            self.send_error(404)
            return
        try:
            subprocess.run([CONSOLE_BIN], check=True, timeout=15)
            self._json(200, {"ok": True, "message": "Cambiando a consola…"})
        except subprocess.CalledProcessError:
            self._json(500, {"ok": False, "error": "No se pudo activar modo consola."})
        except subprocess.TimeoutExpired:
            self._json(500, {"ok": False, "error": "Tiempo de espera agotado."})


def main() -> None:
    HTTPServer((HOST, PORT), ModeHandler).serve_forever()


if __name__ == "__main__":
    main()
