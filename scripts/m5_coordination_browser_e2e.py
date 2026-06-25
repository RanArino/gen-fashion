#!/usr/bin/env python3
import argparse
import base64
import hashlib
import http.server
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class DevToolsSocket:
    def __init__(self, websocket_url: str):
        parsed = urlparse(websocket_url)
        self._host = parsed.hostname or "localhost"
        self._port = parsed.port or 80
        self._path = parsed.path
        if parsed.query:
            self._path += f"?{parsed.query}"
        self._socket = socket.create_connection((self._host, self._port), timeout=10)
        self._next_id = 1
        self._connect()

    def _connect(self) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self._path} HTTP/1.1\r\n"
            f"Host: {self._host}:{self._port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self._socket.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += self._socket.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"WebSocket upgrade failed: {response!r}")
        accept = base64.b64encode(
            hashlib.sha1((key + GUID).encode("ascii")).digest()
        ).decode("ascii")
        if f"Sec-WebSocket-Accept: {accept}".encode("ascii") not in response:
            raise RuntimeError("WebSocket accept header mismatch")

    def call(self, method: str, params: dict | None = None, timeout: float = 30) -> dict:
        message_id = self._next_id
        self._next_id += 1
        self._send_json({"id": message_id, "method": method, "params": params or {}})
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = self._recv_json()
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(f"CDP {method} failed: {message['error']}")
                return message.get("result", {})
        raise RuntimeError(f"Timed out waiting for CDP response to {method}")

    def close(self) -> None:
        self._socket.close()

    def _send_json(self, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        header = bytearray([0x81])
        if len(data) < 126:
            header.append(0x80 | len(data))
        elif len(data) < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", len(data)))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", len(data)))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self._socket.sendall(bytes(header) + masked)

    def _recv_json(self) -> dict:
        while True:
            first, second = self._read_exact(2)
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            masked = second & 0x80
            mask = self._read_exact(4) if masked else b""
            payload = self._read_exact(length)
            if masked:
                payload = bytes(
                    byte ^ mask[index % 4] for index, byte in enumerate(payload)
                )
            if opcode == 0x8:
                raise RuntimeError("Chrome closed the WebSocket")
            if opcode == 0x9:
                continue
            if opcode == 0x1:
                return json.loads(payload.decode("utf-8"))

    def _read_exact(self, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = self._socket.recv(size - len(data))
            if not chunk:
                raise RuntimeError("WebSocket closed unexpectedly")
            data += chunk
        return data


def wait_for_debug_page(port: int) -> str:
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urlopen(f"http://localhost:{port}/json", timeout=2) as response:
                pages = json.loads(response.read().decode("utf-8"))
            for page in pages:
                if page.get("type") == "page":
                    return page["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("Chrome DevTools endpoint did not become available")


def run_server(directory: Path, port: int) -> http.server.ThreadingHTTPServer:
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
        *args, directory=str(directory), **kwargs
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def evaluate_json(cdp: DevToolsSocket, expression: str) -> object:
    result = cdp.call(
        "Runtime.evaluate",
        {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": False,
        },
    )
    remote = result.get("result", {})
    if "value" in remote:
        return remote["value"]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M5 rendered browser E2E.")
    parser.add_argument("--build-dir", default="flutter-web-app/build/web")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--debug-port", type=int, default=9222)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--screenshot", default="/tmp/m5-browser-e2e.png")
    args = parser.parse_args()

    build_dir = Path(args.build_dir).resolve()
    if not (build_dir / "index.html").exists():
        raise RuntimeError(f"Missing Flutter Web build at {build_dir}")

    chrome = shutil.which("google-chrome") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not Path(chrome).exists():
        raise RuntimeError("Google Chrome was not found")

    server = run_server(build_dir, args.port)
    profile = tempfile.TemporaryDirectory(prefix="m5-chrome-profile-")
    chrome_proc = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--remote-debugging-port={args.debug_port}",
            f"--user-data-dir={profile.name}",
            f"http://localhost:{args.port}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    cdp = None
    try:
        cdp = DevToolsSocket(wait_for_debug_page(args.debug_port))
        cdp.call("Runtime.enable")
        cdp.call("Page.enable")

        deadline = time.time() + args.timeout_seconds
        state = None
        while time.time() < deadline:
            raw_state = evaluate_json(
                cdp,
                "window.localStorage && window.localStorage.getItem('m5_e2e_state')",
            )
            if raw_state:
                state = json.loads(raw_state)
                if (
                    state.get("status") == "COMPLETED"
                    and state.get("hasResult") is True
                    and {"tool_call", "tool_result"}.issubset(
                        set(state.get("eventKinds", []))
                    )
                    and {"search_closet", "style_synthesizer"}.issubset(
                        set(state.get("toolNames", []))
                    )
                ):
                    break
                if state.get("error"):
                    raise RuntimeError(f"Rendered app reported error: {state}")
            time.sleep(1)
        else:
            raise RuntimeError(f"Timed out waiting for M5 browser completion: {state}")

        screenshot = cdp.call(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": True},
            timeout=10,
        )
        Path(args.screenshot).write_bytes(base64.b64decode(screenshot["data"]))
        print(json.dumps({"state": state, "screenshot": args.screenshot}, indent=2))
    finally:
        if cdp is not None:
            cdp.close()
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome_proc.kill()
        profile.cleanup()
        server.shutdown()


if __name__ == "__main__":
    main()
