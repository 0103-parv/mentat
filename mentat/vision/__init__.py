"""Grounded vision — Jarvis actually LOOKS through the Mac's camera, native + verified.

Replicates the genuinely-buildable core of the driftworks demos (intruder/person detection,
presence) using Apple's AVFoundation + Vision via a tiny Swift binary — no installs, no model
downloads, runs on the CPU/Neural Engine. The honest fit: a detection is CHECKABLE (how many
faces/people, with confidence), so this is grounded perception — what the camera really sees —
not the model imagining. Physical camera-panning / robot embodiment need hardware we don't have.

Needs one-time CAMERA PERMISSION for the process that runs it (macOS prompts on first real grant;
or System Settings > Privacy & Security > Camera).

  python3 -m mentat.vision          # look once, report what's in frame
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "look.swift"
BIN = HERE / "look"


def _ensure_binary() -> bool:
    if BIN.exists():
        return True
    if not SRC.exists():
        return False
    try:
        subprocess.run(["swiftc", str(SRC), "-o", str(BIN)], check=True,
                       capture_output=True, timeout=180)
    except Exception:
        return False
    return BIN.exists()


def look(timeout: float = 12.0) -> dict:
    """Capture one frame and detect faces/people. Returns {faces, people, confidences} or {error}."""
    if not _ensure_binary():
        return {"error": "could not build the vision tool (needs Xcode command-line tools: xcode-select --install)"}
    try:
        r = subprocess.run([str(BIN)], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": "camera timed out"}
    except Exception as e:
        return {"error": type(e).__name__}
    line = next((ln for ln in reversed(r.stdout.strip().splitlines()) if ln.startswith("{")), "")
    try:
        return json.loads(line)
    except ValueError:
        return {"error": (r.stdout or r.stderr or "no output").strip()[:120]}


_DENIED = ("I can't see — the camera didn't deliver a frame, which means camera access isn't "
           "granted to this process. Grant it in System Settings > Privacy & Security > Camera "
           "(or run me from Terminal once and approve the prompt), then ask again.")


def describe() -> str:
    """An honest, grounded report of what the camera ACTUALLY sees — verified by the detector."""
    o = look()
    if "error" in o:
        e = o["error"]
        if "timed out" in e or "no frame" in e or "access" in e:
            return _DENIED
        return f"I couldn't look — {e}."
    faces, people = int(o.get("faces", 0)), int(o.get("people", 0))
    if faces == 0 and people == 0:
        return "Camera's on and I looked — nobody in frame right now. (Real detection, not a guess.)"
    parts = []
    if faces:
        parts.append(f"{faces} face{'s' if faces != 1 else ''}")
    if people and people != faces:
        parts.append(f"{people} {'people' if people != 1 else 'person'}")
    conf = [float(c) for c in (o.get("confidences") or [])]
    tail = f", top confidence {max(conf) * 100:.0f}%" if conf else ""
    return f"I see {' and '.join(parts)} in frame{tail}. That's a real detection, gated by Apple's Vision."


def main() -> int:
    print("GROUNDED VISION — looking through the Mac camera (native AVFoundation + Vision)\n")
    print(" ", describe())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
