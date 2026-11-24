#!/usr/bin/env python3
"""Static server for the onboarding site, with caching switched off.

`python -m http.server` sends no Cache-Control, so a browser is free to reuse a
stale app.js or style.css.  During development that makes a correct fix look
broken, and mixed HTML/CSS/JS versions produce symptoms that belong to no single
build.  This sends no-store on everything.

    python site/serve.py            # PORT from env, or 8000
    python site/serve.py 9000
"""
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class NoCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):  # quiet
        pass


def main() -> int:
    port = int(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PORT", "8000"))
    root = os.path.dirname(os.path.abspath(__file__))
    handler = partial(NoCache, directory=root)
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"serving {root} on http://127.0.0.1:{port} (no-store)")
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
