#!/usr/bin/env python3
import http.server
import socketserver
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PORT = 8765


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def main():
    import os

    os.chdir(ROOT)
    with socketserver.TCPServer(("127.0.0.1", PORT), QuietHandler) as httpd:
        url = f"http://127.0.0.1:{PORT}/tools/Asobipedia/index.html"
        print(f"Serving Asobipedia viewer at {url}")
        print("Press Ctrl+C to stop.")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        httpd.serve_forever()


if __name__ == "__main__":
    main()
