"""A minimal fake WLED device, just enough of the JSON API for the
test suite: /json/info, /json/state (GET and POST), /presets.json.

No real hardware needed to run the suite. This is intentionally a
small hand-rolled HTTPServer rather than a second FastAPI app, so it
can't accidentally inherit any behavior from the real app it's
standing in for.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

INFO = {
    "mac": "aabbccddeeff",
    "name": "Test Light",
    "ver": "0.14.0",
    "leds": {"count": 30, "maxseg": 2},
    "fxcount": 80,
    "palcount": 47,
    "wifi": {"bssid": "aa:bb:cc:dd:ee:ff", "signal": 88, "channel": 6},
}
PRESETS = {"0": {}, "1": {"n": "Warm Glow"}, "5": {"n": "Movie Night"}}


class _Handler(BaseHTTPRequestHandler):
    # Shared across all instances/requests; intentionally simple. No
    # current test depends on /json/state reflecting a specific prior
    # value, so the mutation from POST persisting across tests within
    # a session isn't a real isolation problem today. Worth revisiting
    # if a future test ever needs a pristine GET /json/state.
    state = {"on": True, "bri": 128, "seg": [{"col": [[255, 160, 0]], "fx": 0, "pal": 0}]}

    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/json/info":
            self._send(200, INFO)
        elif self.path == "/json/state":
            self._send(200, _Handler.state)
        elif self.path == "/presets.json":
            self._send(200, PRESETS)
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        if self.path == "/json/state":
            _Handler.state.update(body)
            self._send(200, {"state": _Handler.state})
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args) -> None:
        pass  # quiet; pytest output is noisy enough without this


def start(port: int = 0) -> tuple[HTTPServer, int]:
    """Starts the server on a background daemon thread. Pass port=0
    (the default) to let the OS pick a free port; the actual bound
    port is returned alongside the server."""
    server = HTTPServer(("127.0.0.1", port), _Handler)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, actual_port
