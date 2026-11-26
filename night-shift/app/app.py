"""shop: a tiny web service for the night-shift exercise.

GET /        {"version": "1", "host": "<container name>"}
GET /health  200 when ready, 503 while shutting down

On start it waits STARTUP_SECONDS before it listens, like a service that connects to its database first.
On SIGTERM it stops reporting healthy, keeps answering for DRAIN_SECONDS, then exits 0.
Standard library only.
"""
import json
import os
import signal
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = os.environ.get("VERSION", "1")
PORT = int(os.environ.get("PORT", "8000"))
STARTUP = float(os.environ.get("STARTUP_SECONDS", "3"))
DRAIN = float(os.environ.get("DRAIN_SECONDS", "2"))
HOST = socket.gethostname()

server = None
draining = False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            code, body = (503, b"draining\n") if draining else (200, b"ok\n")
            ctype = "text/plain"
        else:
            code = 200
            body = (json.dumps({"version": VERSION, "host": HOST}) + "\n").encode()
            ctype = "application/json"
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def on_sigterm(*_):
    global draining
    if server is None:
        sys.exit(0)
    draining = True
    print(f"shop v{VERSION}: SIGTERM, answering {DRAIN:g} s more", flush=True)
    threading.Timer(DRAIN, server.shutdown).start()


def main():
    global server
    signal.signal(signal.SIGTERM, on_sigterm)
    print(f"shop v{VERSION} on {HOST}: loading for {STARTUP:g} s", flush=True)
    time.sleep(STARTUP)
    server = ThreadingHTTPServer(("", PORT), Handler)
    print(f"shop v{VERSION} on {HOST}: listening on :{PORT}", flush=True)
    server.serve_forever()
    print(f"shop v{VERSION} on {HOST}: stopped", flush=True)


if __name__ == "__main__":
    main()
