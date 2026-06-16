"""The reasoning core — an LLM proposer for the Mentat kernel.

This is the swap-point the kernel was built around: replace mutation with real
reasoning. The core proposes candidates; the kernel's verifier still gates every
one of them, so the core is never trusted blindly — only its *verified* output
survives.

Kept deliberately robust: the network call degrades gracefully (it tries
adaptive thinking, falls back if the SDK/model doesn't accept it), and the key
is read from the environment or a .env file. If neither the `anthropic` SDK nor
a key is present, `core_available()` returns False and callers fall back to the
offline proposer — the loop never starves.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

# Per house rules: default to the most capable model. Override with MENTAT_MODEL
# (e.g. claude-haiku-4-5) for cheap, high-volume proposing.
DEFAULT_MODEL = "claude-opus-4-8"


def _load_key() -> str | None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    candidates = []
    if os.environ.get("MENTAT_ENV"):
        candidates.append(Path(os.environ["MENTAT_ENV"]))
    candidates += [Path.cwd() / ".env",
                   Path(__file__).resolve().parent.parent / ".env",
                   Path.home() / ".env"]
    for p in candidates:
        try:
            if p.is_file():
                for line in p.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("ANTHROPIC_API_KEY"):
                        _, _, val = line.partition("=")
                        val = val.strip().strip('"').strip("'")
                        if val:
                            return val
        except OSError:
            pass
    return None


def core_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return _load_key() is not None


def extract_json_list(text: str) -> list[str]:
    """Tolerantly pull a list of candidate strings out of a model response.

    Prefers a JSON array; falls back to one-candidate-per-line so a stray
    sentence of preamble never breaks the loop."""
    m = re.search(r"\[.*\]", text, re.S)
    if m:
        try:
            arr = json.loads(m.group(0))
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except (json.JSONDecodeError, ValueError):
            pass
    out = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*0123456789.) ").strip().strip("`").strip()
        if line and any(c in line for c in "x0123456789"):
            out.append(line)
    return out


def extract_code_blocks(text: str) -> list[str]:
    """Pull fenced ```python code blocks (each a candidate program) from a reply.

    Robust for multi-line code where a JSON array would be fragile to escape."""
    blocks = [b.strip() for b in re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.S)]
    blocks = [b for b in blocks if "def build" in b]
    if blocks:
        return blocks
    return [text.strip()] if "def build" in text else []


@dataclass
class AnthropicCore:
    """Claude-backed proposer. One method: turn a prompt into candidate strings."""
    model: str = field(default_factory=lambda: os.environ.get("MENTAT_MODEL", DEFAULT_MODEL))
    thinking: bool = True
    _client: object = field(default=None, repr=False)

    def _anthropic(self):
        import anthropic
        if self._client is None:
            key = _load_key()
            self._client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        return anthropic

    def complete_text(self, system: str, user: str, *, max_tokens: int = 2048) -> str:
        anthropic = self._anthropic()
        base = dict(model=self.model, max_tokens=max_tokens, system=system,
                    messages=[{"role": "user", "content": user}])
        try:
            resp = (self._client.messages.create(**base, thinking={"type": "adaptive"})
                    if self.thinking else self._client.messages.create(**base))
        except anthropic.BadRequestError:
            # SDK/model that doesn't accept the adaptive-thinking param — retry plain.
            resp = self._client.messages.create(**base)
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


@dataclass
class ScriptedCore:
    """A deterministic stand-in for tests — returns canned responses in order.

    Lets the LLM-proposer path be tested end-to-end with no network and no key."""
    responses: list[str]
    i: int = 0

    def complete_text(self, system: str, user: str, *, max_tokens: int = 2048) -> str:
        out = self.responses[min(self.i, len(self.responses) - 1)]
        self.i += 1
        return out
