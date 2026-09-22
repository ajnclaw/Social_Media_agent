# image_server.py
#
# Minimal HTTP server exposing SD-Turbo image generation, meant to run
# on a separate machine with its own GPU -- create_video calls this
# over the network instead of loading the model locally, so it doesn't
# compete with Chatterbox for VRAM on the main laptop.
#
# Run on the machine that should do image generation with:
#   .venv/bin/python -m agent.image_server

import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .image_gen import generate_image


HOST = "0.0.0.0"
PORT = 8420


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/generate":
            self.send_error(404, "Not found")
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            prompt = body["prompt"]

            image = generate_image(prompt)

            buffer = io.BytesIO()
            image.save(buffer, format="PNG")

            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(buffer.tell()))
            self.end_headers()
            self.wfile.write(buffer.getvalue())

        except Exception as exc:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))

    def log_message(self, format, *args):
        print(f"[image_server] {self.address_string()} - {format % args}")


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Image server listening on {HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
