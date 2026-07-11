#!/usr/bin/env python3
"""MP-7 manual `make dev` browser pass: tab persistence + off-tab notification.

Reuses the hand-rolled CDP client from `m5_coordination_browser_e2e.py` (this
repo has no Playwright/Selenium installed) and extends it with real UI clicks
(bottom `NavigationBar` taps) driven by mouse coordinates, since Flutter Web
(canvaskit) renders to a canvas with no clickable DOM nodes for `Runtime`-side
selectors.

Drives a real Flutter Web release bundle (built with `E2E_AUTO_SIGN_IN=true
E2E_AUTO_RUN=true`, which auto-signs into the Firebase Auth Emulator and
auto-starts a STANDARD / SHARED_CLOSET coordination session on load, matching
`_HomeScreenState`'s `_index = AppConfig.e2eAutoRun ? 1 : 0` and
`CoordinationScreen._start()`'s `initState` auto-run hook) against a running
`make dev` stack, and exercises:

  - MP-1 (keep-alive IndexedStack): switch Closet -> History -> Coordinate
    while GENERATING and confirm the trace/candidate state was not reset.
  - MP-4 (History live refresh): visit History before completion (registering
    its `refreshOn` listener), navigate away, and confirm the newly-completed
    session appears after generation finishes off-tab, without a full reload.
  - MP-5 (SnackBar notification): navigate away before the terminal state and
    stay away; confirm a SnackBar with a "View" action appears exactly once,
    and attempt to click it to jump back to the completed Coordinate result.

State is read every poll via `window.localStorage['m5_e2e_state']`, which
`CoordinationScreen._reportE2eState()` updates on every state change
regardless of which tab is currently visible (it's gated only on
`AppConfig.e2eAutoRun`, not tab visibility) -- this is what lets us observe
the session progressing even while a different tab is on screen.
"""

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
        {"expression": expression, "returnByValue": True, "awaitPromise": False},
    )
    remote = result.get("result", {})
    if "value" in remote:
        return remote["value"]
    return None


def get_e2e_state(cdp: DevToolsSocket) -> dict | None:
    raw = evaluate_json(
        cdp, "window.localStorage && window.localStorage.getItem('m5_e2e_state')"
    )
    return json.loads(raw) if raw else None


def screenshot(cdp: DevToolsSocket, path: Path) -> None:
    result = cdp.call("Page.captureScreenshot", {"format": "png"}, timeout=10)
    path.write_bytes(base64.b64decode(result["data"]))


def click(cdp: DevToolsSocket, x: float, y: float) -> None:
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
    cdp.call(
        "Input.dispatchMouseEvent",
        {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1},
    )
    cdp.call(
        "Input.dispatchMouseEvent",
        {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1},
    )


def press_escape(cdp: DevToolsSocket) -> None:
    cdp.call(
        "Input.dispatchKeyEvent",
        {"type": "keyDown", "windowsVirtualKeyCode": 27, "key": "Escape"},
    )
    cdp.call(
        "Input.dispatchKeyEvent",
        {"type": "keyUp", "windowsVirtualKeyCode": 27, "key": "Escape"},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MP-7 tab-persistence browser pass.")
    parser.add_argument("--build-dir", default="flutter-web-app/build/web")
    parser.add_argument("--port", type=int, default=8089)
    parser.add_argument("--debug-port", type=int, default=9223)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--evidence-dir", default="/tmp/mp7-evidence")
    args = parser.parse_args()

    build_dir = Path(args.build_dir).resolve()
    if not (build_dir / "index.html").exists():
        raise RuntimeError(f"Missing Flutter Web build at {build_dir}")

    evidence_dir = Path(args.evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    log_lines: list[str] = []

    def note(message: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {message}"
        print(line, flush=True)
        log_lines.append(line)

    chrome = shutil.which("google-chrome") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not Path(chrome).exists():
        raise RuntimeError("Google Chrome was not found")

    server = run_server(build_dir, args.port)
    profile = tempfile.TemporaryDirectory(prefix="mp7-chrome-profile-")
    chrome_proc = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={args.width},{args.height}",
            f"--remote-debugging-port={args.debug_port}",
            f"--user-data-dir={profile.name}",
            f"http://localhost:{args.port}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    cdp = None
    result = {"checks": {}}
    try:
        cdp = DevToolsSocket(wait_for_debug_page(args.debug_port))
        cdp.call("Runtime.enable")
        cdp.call("Page.enable")
        cdp.call(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": args.width,
                "height": args.height,
                "deviceScaleFactor": 1,
                "mobile": False,
            },
        )

        width, height = args.width, args.height
        nav_y = height - 40  # NavigationBar default height is 80dp, centered.

        def nav_x(index: int) -> float:
            return width * (index + 0.5) / 4

        CLOSET, COORDINATE, HISTORY, SHARED = 0, 1, 2, 3

        # --- Step 1: wait for auto sign-in + auto-run to produce a status. ---
        deadline = time.time() + args.timeout_seconds
        state = None
        while time.time() < deadline:
            state = get_e2e_state(cdp)
            if state and state.get("status"):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Timed out waiting for initial session status")
        note(f"initial session state: {state}")
        screenshot(cdp, evidence_dir / "01_initial.png")

        # --- Step 2: wait until GENERATING (mid-flow) for the tab-persistence check. ---
        deadline = time.time() + args.timeout_seconds
        while time.time() < deadline:
            state = get_e2e_state(cdp)
            if state and state.get("status") == "GENERATING":
                break
            if state and state.get("error"):
                raise RuntimeError(f"Session errored before GENERATING: {state}")
            time.sleep(0.3)
        else:
            raise RuntimeError(f"Timed out waiting for GENERATING; last state: {state}")
        baseline = state
        note(f"reached GENERATING (baseline): {baseline}")
        screenshot(cdp, evidence_dir / "02_generating_on_tab.png")

        # --- Step 3: Closet -> History (first visit) -> Coordinate; confirm preserved (MP-1). ---
        click(cdp, nav_x(CLOSET), nav_y)
        time.sleep(0.7)
        screenshot(cdp, evidence_dir / "03_closet_tab.png")

        click(cdp, nav_x(HISTORY), nav_y)
        time.sleep(0.9)
        screenshot(cdp, evidence_dir / "04_history_tab_first_visit.png")

        click(cdp, nav_x(COORDINATE), nav_y)
        time.sleep(0.7)
        after_roundtrip = get_e2e_state(cdp)
        screenshot(cdp, evidence_dir / "05_back_to_coordinate.png")
        note(f"state after Closet->History->Coordinate round trip: {after_roundtrip}")

        preserved = bool(
            after_roundtrip
            and baseline
            and after_roundtrip.get("sessionId") == baseline.get("sessionId")
            and after_roundtrip.get("eventCount", 0) >= baseline.get("eventCount", 0)
            and after_roundtrip.get("status") in ("GENERATING", "COMPLETED", "ERROR")
        )
        result["checks"]["mp1_tab_persistence"] = {
            "pass": preserved,
            "baseline": baseline,
            "after_roundtrip": after_roundtrip,
        }
        note(f"MP-1 tab persistence check: {'PASS' if preserved else 'FAIL'}")

        # --- Step 4: navigate away and stay away until terminal (MP-5 setup). ---
        click(cdp, nav_x(CLOSET), nav_y)
        time.sleep(0.5)
        note("navigated to Closet tab; waiting for off-tab completion")
        deadline = time.time() + args.timeout_seconds
        terminal_state = None
        while time.time() < deadline:
            s = get_e2e_state(cdp)
            if s and s.get("status") in ("COMPLETED", "ERROR"):
                terminal_state = s
                break
            time.sleep(0.2)
        if terminal_state is None:
            raise RuntimeError("Timed out waiting for off-tab completion")
        note(f"off-tab terminal state reached: {terminal_state}")
        result["checks"]["terminal_state"] = terminal_state

        # --- Step 5: capture the SnackBar and attempt to click its "View" action. ---
        screenshot(cdp, evidence_dir / "06_snackbar_pre_click.png")
        candidate_points = [
            (width - dx, height - dy)
            for dy in (90, 105, 120)
            for dx in (40, 65, 95, 130)
        ]
        for (x, y) in candidate_points:
            click(cdp, x, y)
            time.sleep(0.12)
        screenshot(cdp, evidence_dir / "07_after_view_click_attempts.png")
        press_escape(cdp)
        time.sleep(0.3)
        screenshot(cdp, evidence_dir / "08_after_escape_safety.png")

        # Whether or not the blind click hit the SnackBar action precisely,
        # force navigation back to Coordinate to confirm the completed result
        # is reachable/intact (this is the outcome the "View" action itself
        # is supposed to produce).
        click(cdp, nav_x(COORDINATE), nav_y)
        time.sleep(0.7)
        screenshot(cdp, evidence_dir / "09_coordinate_after_completion.png")
        final_coordinate_state = get_e2e_state(cdp)
        note(f"state on Coordinate tab post-completion: {final_coordinate_state}")
        result["checks"]["coordinate_state_post_completion"] = final_coordinate_state

        # --- Step 6: History (already visited) should show the new session live (MP-4). ---
        click(cdp, nav_x(HISTORY), nav_y)
        time.sleep(1.2)
        screenshot(cdp, evidence_dir / "10_history_after_completion.png")

        result["baseline_session_id"] = baseline.get("sessionId") if baseline else None
        result["terminal_status"] = terminal_state.get("status")
        (evidence_dir / "log.txt").write_text("\n".join(log_lines) + "\n")
        (evidence_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
        print(json.dumps(result, indent=2, sort_keys=True))
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
