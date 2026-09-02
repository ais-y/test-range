#!/usr/bin/env python3
"""Write a fixed banner to every TCP client, then close. No real service."""

import os
import socketserver

# BANNER may carry \r \n \xNN escapes; decode them from the env string.
BANNER = os.environ.get("BANNER", "range-banner\r\n").encode().decode("unicode_escape")
PORT = int(os.environ.get("PORT", "9000"))


class BannerHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.sendall(BANNER.encode("latin-1", "replace"))


if __name__ == "__main__":
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), BannerHandler) as srv:
        srv.serve_forever()
