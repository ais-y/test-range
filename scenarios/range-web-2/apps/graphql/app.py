#!/usr/bin/env python3
"""GraphQL endpoint with introspection enabled. Static minimal schema, no data."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

# Minimal introspection response so a __schema query resolves.
SCHEMA = {"data": {"__schema": {"queryType": {"name": "Query"},
          "types": [{"kind": "OBJECT", "name": "Query", "fields": [
              {"name": "range", "type": {"name": "String"}}]}]}}}


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        out = SCHEMA if "__schema" in body else {"data": {"range": "ok"}}
        self.wfile.write(json.dumps(out).encode())

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"POST GraphQL queries here (introspection enabled)\n")

    def log_message(self, *_):
        pass


HTTPServer(("0.0.0.0", 8080), H).serve_forever()
