"""Secrets layer — so mentat/Jarvis can USE credentials you've authorized without you
re-entering them every run.

This is the normal way automated agents handle credentials (CI, cron, deploy bots):
store a secret ONCE in a store the process is allowed to read, then read it at
runtime. It is NOT about bypassing anyone's security — it only surfaces credentials
you deliberately stored for your own system.

Resolution order for `get_secret(NAME)`:
  1. environment variable  NAME
  2. macOS Keychain        service "mentat:NAME"   (stored once, encrypted at rest)
  3. a gitignored .env      NAME=...   (env, ~/mentat, ~/swechats, ~/)

Values are NEVER logged, printed, or returned by the listing commands. Store one with:
    python3 -m mentat.secrets set ELEVENLABS_API_KEY     # prompts hidden, saves to Keychain
    python3 -m mentat.secrets list                       # names only, never values
    python3 -m mentat.secrets check ELEVENLABS_API_KEY   # says present/missing, not the value
"""
from __future__ import annotations

import getpass
import os
import subprocess
import sys
from pathlib import Path

KEYCHAIN_SERVICE = "mentat"
_ENV_FILES = [
    Path.cwd() / ".env",
    Path.home() / "mentat" / ".env",
    Path.home() / "swechats" / ".env",
    Path.home() / ".env",
]


def _account() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USER", "mentat")


def _from_keychain(name: str) -> str | None:
    """Read from the macOS login Keychain (encrypted at rest). No-op off macOS."""
    if sys.platform != "darwin":
        return None
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-a", _account(),
             "-s", f"{KEYCHAIN_SERVICE}:{name}", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            val = r.stdout.rstrip("\n")
            return val or None
    except Exception:
        return None
    return None


def _parse_env_file(path: Path, name: str) -> str | None:
    try:
        if not path.is_file():
            return None
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, val = line.partition("=")
            if not sep or key.strip().removeprefix("export ").strip() != name:
                continue
            val = val.strip()
            if val[:1] in ("'", '"'):                 # quoted: take exactly what's inside
                end = val.find(val[0], 1)
                return val[1:end] if end != -1 else val[1:]
            return val.split(" #", 1)[0].strip() or None   # unquoted: drop inline comment
    except OSError:
        return None
    return None


def _from_env_files(name: str) -> str | None:
    for path in _ENV_FILES:
        val = _parse_env_file(path, name)
        if val:
            return val
    return None


def get_secret(name: str, *, default: str | None = None) -> str | None:
    """Resolve a secret by name (env -> Keychain -> .env). Never logs the value."""
    return (os.environ.get(name) or _from_keychain(name)
            or _from_env_files(name) or default)


def has_secret(name: str) -> bool:
    return get_secret(name) is not None


def set_secret(name: str, value: str) -> None:
    """Store/replace a secret in the macOS Keychain (encrypted at rest)."""
    if sys.platform != "darwin":
        raise RuntimeError(
            "Keychain storage is macOS-only. Put the secret in a gitignored .env "
            f"as {name}=... or export it as an env var instead.")
    subprocess.run(
        ["security", "add-generic-password", "-a", _account(),
         "-s", f"{KEYCHAIN_SERVICE}:{name}", "-w", value, "-U"],
        check=True, capture_output=True,
    )


# --------------------------------------------------------------------------- #
# CLI — store-once / inspect. Never prints a secret value.                     #
# --------------------------------------------------------------------------- #
def _cli(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: python3 -m mentat.secrets <set NAME | check NAME | where NAME>")
        return 0
    cmd = argv[0]
    if cmd == "set" and len(argv) >= 2:
        name = argv[1]
        value = getpass.getpass(f"value for {name} (hidden): ")
        if not value:
            print("empty value; nothing stored.")
            return 1
        set_secret(name, value)
        print(f"stored {name} in the macOS Keychain (service '{KEYCHAIN_SERVICE}:{name}').")
        return 0
    if cmd == "check" and len(argv) >= 2:
        name = argv[1]
        print(f"{name}: {'present' if has_secret(name) else 'MISSING'}")
        return 0
    if cmd == "where" and len(argv) >= 2:               # which source holds it (not the value)
        name = argv[1]
        src = ("env var" if os.environ.get(name) else
               "Keychain" if _from_keychain(name) else
               ".env file" if _from_env_files(name) else "not found")
        print(f"{name}: {src}")
        return 0
    print("usage: python3 -m mentat.secrets <set NAME | check NAME | where NAME>")
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
