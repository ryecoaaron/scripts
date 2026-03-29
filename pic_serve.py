#!/usr/bin/env python3
"""Simple picture server - serves images from ./pics and lists them on the index page."""

import argparse
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
PORT = 8080


class PicHandler(BaseHTTPRequestHandler):
    pics_dir: Path  # set before server starts

    def do_GET(self):
        path = unquote(self.path)

        if path == "/" or path == "/index.html":
            self.serve_index()
        elif path.startswith("/pics/"):
            self.serve_file(self.pics_dir / path[len("/pics/"):])
        else:
            self.send_error(404)

    def serve_index(self):
        images = sorted(
            f for f in self.pics_dir.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS
        ) if self.pics_dir.exists() else []

        items = "\n".join(
            f'<div class="pic"><a href="/pics/{f.name}"><img src="/pics/{f.name}" loading="lazy"><p>{f.name}</p></a></div>'
            for f in images
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pictures</title>
  <style>
    body {{ font-family: sans-serif; background: #111; color: #eee; margin: 0; padding: 1rem; }}
    h1 {{ text-align: center; }}
    .gallery {{ display: flex; flex-wrap: wrap; gap: 1rem; justify-content: center; }}
    .pic {{ text-align: center; }}
    .pic img {{ max-width: 200px; max-height: 200px; object-fit: cover; border-radius: 6px; display: block; }}
    .pic p {{ margin: 0.3rem 0 0; font-size: 0.8rem; word-break: break-all; max-width: 200px; }}
    p.empty {{ text-align: center; color: #888; }}
  </style>
</head>
<body>
  <h1>Pictures ({len(images)})</h1>
  {'<div class="gallery">' + items + '</div>' if images else '<p class="empty">No images found in ./pics/</p>'}
</body>
</html>"""

        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, path: Path):
        if not path.is_file():
            self.send_error(404)
            return
        mime, _ = mimetypes.guess_type(path)
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", path.stat().st_size)
        self.end_headers()
        with open(path, "rb") as f:
            self.wfile.write(f.read())

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serve images from a directory.")
    parser.add_argument("directory", nargs="?", default="pics", help="Directory of images to serve (default: ./pics)")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to listen on (default: {PORT})")
    args = parser.parse_args()

    PicHandler.pics_dir = Path(args.directory)
    PicHandler.pics_dir.mkdir(exist_ok=True)
    print(f"Serving pictures from {PicHandler.pics_dir} at http://localhost:{args.port}")
    HTTPServer(("", args.port), PicHandler).serve_forever()
