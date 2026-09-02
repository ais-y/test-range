#!/usr/bin/env python3
"""Admin panel accepting the documented default credential admin:admin.

The account is a fake, range-only login. Behind it is a single static page - no
real admin functionality, no data.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

LOGIN = (b'<title>Admin Portal</title><form method=post action=/login>'
         b'<input name=user><input name=pass type=password>'
         b'<button>Sign in</button></form>')


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self._send(200, LOGIN)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(n).decode())
        ok = form.get("user") == ["admin"] and form.get("pass") == ["admin"]
        self._send(200 if ok else 401,
                   b"range admin dashboard\n" if ok else b"invalid\n")

    def _send(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


HTTPServer(("0.0.0.0", 8080), H).serve_forever()
