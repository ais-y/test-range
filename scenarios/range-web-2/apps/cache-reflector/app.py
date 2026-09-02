#!/usr/bin/env python3
"""Reflects an unkeyed X-Forwarded-Host into an absolute URL - the classic
web-cache-poisoning shape. Serves a cache-friendly response; no cache here does
the poisoning, the detector just needs to see the unkeyed reflection.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        host = self.headers.get("X-Forwarded-Host", "range")
        body = f'<link rel="canonical" href="https://{host}/">'.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Cache-Control", "public, max-age=60")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


HTTPServer(("0.0.0.0", 8080), H).serve_forever()
