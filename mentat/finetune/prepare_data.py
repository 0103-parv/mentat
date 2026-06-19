"""Build a finance instruction dataset for LoRA fine-tuning, from the grounded corpus.

Outputs chat-format JSONL (train.jsonl / valid.jsonl) — the format mlx-lm and most
LoRA trainers accept: {"messages": [{"role":"user",...},{"role":"assistant",...}]}.
Deterministic, pure-Python, runnable now. This is a SEED set from the local docs; for a
real fine-tune, expand the corpus or merge a public finance instruction dataset (see
README.md).

  python3 -m mentat.finetune.prepare_data
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "finance_docs"
OUT = Path(__file__).resolve().parent / "data"


def _pairs(docs_dir: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for f in sorted(docs_dir.glob("*.md")):
        lines = f.read_text(encoding="utf-8").strip().splitlines()
        title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("#") else f.stem
        body = "\n".join(line for line in lines[1:] if line.strip()).strip()
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        if not paras:
            continue
        pairs.append((f"Explain {title.lower()} in quantitative finance.",
                      " ".join(paras)))                      # full-concept pair
        for p in paras:                                      # focused per-paragraph pairs
            head = " ".join(p.split()[:6])
            pairs.append((f"In quantitative finance, explain this aspect of "
                          f"{title.lower()}: \"{head}...\"", p))
    return pairs


def build(out: Path | str = OUT, docs_dir: Path | str = DOCS,
          valid_frac: float = 0.2) -> tuple[int, int]:
    out, docs_dir = Path(out), Path(docs_dir)
    out.mkdir(parents=True, exist_ok=True)
    pairs = _pairs(docs_dir)
    cut = max(1, int(len(pairs) * (1 - valid_frac)))

    def fmt(q: str, a: str) -> str:
        return json.dumps({"messages": [{"role": "user", "content": q},
                                        {"role": "assistant", "content": a}]})

    (out / "train.jsonl").write_text("\n".join(fmt(q, a) for q, a in pairs[:cut]))
    (out / "valid.jsonl").write_text("\n".join(fmt(q, a) for q, a in pairs[cut:]))
    return cut, len(pairs) - cut


def main() -> int:
    n_train, n_valid = build()
    print(f"wrote {n_train} train + {n_valid} valid finance instruction examples to {OUT}")
    print("(SEED set from the local corpus — expand it for a real fine-tune; see README.md)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
