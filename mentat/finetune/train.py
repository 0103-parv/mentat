"""Run a cheap LoRA fine-tune — free + local on Apple Silicon via mlx-lm.

If mlx-lm is installed it launches LoRA training on a small instruct model; otherwise it
prints the exact install + command (so the path is ready either way). For a non-Mac /
cloud route (peft + transformers), see README.md.

  python3 -m mentat.finetune.train            # train locally (after prepare_data)
  python3 -m mentat.finetune.train --iters 300
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
ADAPTERS = Path(__file__).resolve().parent / "adapters"
# Small, instruct, 4-bit — trains in minutes on an M-series Mac, $0.
MODEL = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"


def main() -> int:
    iters = "200"
    if "--iters" in sys.argv:
        iters = sys.argv[sys.argv.index("--iters") + 1]
    if not (DATA / "train.jsonl").exists():
        print("No dataset yet. Run:  python3 -m mentat.finetune.prepare_data")
        return 1
    cmd = [sys.executable, "-m", "mlx_lm.lora", "--model", MODEL, "--train",
           "--data", str(DATA), "--iters", iters, "--batch-size", "1",
           "--adapter-path", str(ADAPTERS)]
    try:
        import mlx_lm  # noqa: F401
    except Exception:
        print("mlx-lm is not installed. To run this free + locally on your Mac:\n")
        print("  uv pip install mlx-lm        # (Apple Silicon; no CUDA, no cost)")
        print("  python3 -m mentat.finetune.prepare_data")
        print("  " + " ".join(cmd))
        print("\nThen chat with the specialized model:")
        print(f"  python3 -m mlx_lm.generate --model {MODEL} --adapter-path {ADAPTERS} "
              "--prompt 'Explain the deflated Sharpe ratio.'")
        return 0
    ADAPTERS.mkdir(exist_ok=True)
    print("running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
