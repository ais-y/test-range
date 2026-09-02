#!/usr/bin/env python3
"""ASP.NET viewstate signed with the PUBLIC badsecrets test key (Machinekey).

The key is a well-known published test value, not a secret - the detector's job
is to notice the viewstate is signed with a crackable/known key. Nothing here
processes an incoming viewstate, so there is no deserialization sink.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer

# __VIEWSTATE MAC'd with the public badsecrets test key (fake/known).
VIEWSTATE = ("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
             "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
PAGE = (
    "<form method=post>"
    f'<input type=hidden name="__VIEWSTATE" value="{VIEWSTATE}">'
    '<input type=hidden name="__VIEWSTATEGENERATOR" value="CA0B0334">'
    "</form>"
).encode()


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *_):
        pass


HTTPServer(("0.0.0.0", 8080), H).serve_forever()
