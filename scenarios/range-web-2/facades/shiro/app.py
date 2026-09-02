#!/usr/bin/env python3
"""Apache Shiro fingerprint: sets a rememberMe cookie. No deserialization sink."""

from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        # rememberMe cookie is the Shiro tell; value is inert padding.
        self.send_header("Set-Cookie", "rememberMe=deleteMe; Path=/")
        self.end_headers()
        self.wfile.write(b"range shiro fingerprint\n")

    def log_message(self, *_):
        pass


HTTPServer(("0.0.0.0", 8080), H).serve_forever()
