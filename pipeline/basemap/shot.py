#!/usr/bin/env python3
"""Headless-Chrome screenshot of a page at a given CSS size, after an awaited JS condition.

    python3 pipeline/basemap/shot.py <url> <w> <h> <out.png> [--dark] [--scale 2] [--wait-js '<expr>'] [--eval-js '<expr>' --eval-out f.json]

Uses Chrome's DevTools protocol over a pipe-less websocket (stdlib only). Used for
the globe page's self-checks (limb profile, hill-shade amplitude); the acceptance
session takes its own screenshots.
"""
import argparse
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class CDP:
    """Tiny DevTools websocket client (RFC 6455 client frames, text only)."""

    def __init__(self, ws_url):
        host, rest = ws_url[5:].split("/", 1)
        h, p = host.split(":")
        self.sock = socket.create_connection((h, int(p)))
        key = base64.b64encode(os.urandom(16)).decode()
        req = f"GET /{rest} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        self.buf = buf.split(b"\r\n\r\n", 1)[1]
        self.id = 0

    def _send(self, payload):
        data = payload.encode()
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126: hdr.append(0x80 | n)
        elif n < 65536: hdr.append(0x80 | 126); hdr += n.to_bytes(2, "big")
        else: hdr.append(0x80 | 127); hdr += n.to_bytes(8, "big")
        mask = os.urandom(4)
        hdr += mask
        self.sock.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _recv_frame(self):
        while True:
            if len(self.buf) >= 2:
                b1 = self.buf[1] & 0x7F
                off = 2
                if b1 == 126:
                    if len(self.buf) < 4: pass
                    else: n = int.from_bytes(self.buf[2:4], "big"); off = 4
                elif b1 == 127:
                    if len(self.buf) < 10: pass
                    else: n = int.from_bytes(self.buf[2:10], "big"); off = 10
                else:
                    n = b1
                if (b1 < 126) or (b1 == 126 and len(self.buf) >= 4) or (b1 == 127 and len(self.buf) >= 10):
                    if len(self.buf) >= off + n:
                        frame = self.buf[off:off + n]; self.buf = self.buf[off + n:]
                        return frame
            chunk = self.sock.recv(1 << 20)
            if not chunk:
                raise EOFError
            self.buf += chunk

    def call(self, method, **params):
        self.id += 1
        self._send(json.dumps({"id": self.id, "method": method, "params": params}))
        while True:
            msg = json.loads(self._recv_frame())
            if msg.get("id") == self.id:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url"); ap.add_argument("w", type=int); ap.add_argument("h", type=int); ap.add_argument("out")
    ap.add_argument("--dark", action="store_true"); ap.add_argument("--scale", type=float, default=1)
    ap.add_argument("--wait-js", default="window.__globe && window.__globe.map.loaded() && window.__globe.map.areTilesLoaded()")
    ap.add_argument("--settle", type=float, default=2.0)
    ap.add_argument("--eval-js"); ap.add_argument("--eval-out")
    a = ap.parse_args()
    port = free_port()
    prof = tempfile.mkdtemp()
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={prof}",
                             f"--window-size={a.w},{a.h}", "--hide-scrollbars", "--use-angle=metal", "--enable-unsafe-swiftshader",
                             "--no-first-run", "--no-default-browser-check", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
                page = next(t for t in tabs if t["type"] == "page")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        cdp = CDP(page["webSocketDebuggerUrl"])
        cdp.call("Emulation.setDeviceMetricsOverride", width=a.w, height=a.h, deviceScaleFactor=a.scale, mobile=False)
        cdp.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark" if a.dark else "light"}])
        cdp.call("Page.enable"); cdp.call("Runtime.enable")
        cdp.call("Page.navigate", url=a.url)
        t0 = time.time()
        while time.time() - t0 < 120:
            r = cdp.call("Runtime.evaluate", expression=f"!!({a.wait_js})", returnByValue=True)
            if r.get("result", {}).get("value"):
                break
            time.sleep(0.5)
        else:
            print("timeout waiting for", a.wait_js, file=sys.stderr)
        time.sleep(a.settle)
        if a.eval_js:
            r = cdp.call("Runtime.evaluate", expression=a.eval_js, returnByValue=True, awaitPromise=True)
            val = r.get("result", {}).get("value")
            if a.eval_out:
                json.dump(val, open(a.eval_out, "w"), indent=1)
            else:
                print(json.dumps(val))
        shot = cdp.call("Page.captureScreenshot", format="png", captureBeyondViewport=False)
        open(a.out, "wb").write(base64.b64decode(shot["data"]))
        print("ok", a.out)
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
