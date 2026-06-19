# LoRA fine-tune path — cheap, one-time finance specialization

The honest way to "specialize the model": **LoRA** (low-rank adaptation) of a small open
model on finance data — NOT training from scratch. LoRA trains a tiny set of adapter
weights (millions of params, not billions), so it's fast and cheap and keeps the base
model's general reasoning. This is the FinGPT approach (~$300 cloud); on your Mac it's **$0**.

## Run it free + locally on your Mac (Apple Silicon, MLX)
```bash
uv pip install mlx-lm                         # free; no CUDA needed
python3 -m mentat.finetune.prepare_data       # build the dataset from the corpus
python3 -m mentat.finetune.train --iters 200  # LoRA-trains a 0.5B instruct model, minutes, $0
# chat with the specialized model:
python3 -m mlx_lm.generate \
  --model mlx-community/Qwen2.5-0.5B-Instruct-4bit \
  --adapter-path mentat/finetune/adapters \
  --prompt "Explain the deflated Sharpe ratio."
```
`train.py` prints these commands if mlx-lm isn't installed, so the path is ready either way.

## Cloud / non-Mac alternative (peft + transformers)
~$ a few on a rented GPU: `pip install peft transformers datasets accelerate`, load a small
base (e.g. Qwen2.5-0.5B-Instruct), wrap with a LoRA config (r=8, alpha=16, target the
attention projections), train on `data/train.jsonl`. Same dataset format.

## Honest notes
- **The dataset here is a SEED** built from `mentat/finance_docs/` (a few dozen examples).
  A few dozen examples will barely move a model. For a real specialization, **expand it**:
  add more docs to `finance_docs/`, or merge a public finance instruction dataset
  (e.g. FinGPT's instruction data, or finance Q&A sets on Hugging Face) into `data/`.
- **LoRA specializes STYLE/format and surface knowledge well; it does not add reliable new
  FACTS** — for facts, the RAG (`mentat.rag`) is the right tool. Best results: a lightly
  fine-tuned model + RAG grounding + the verification gate. That's the full stack.
- Adapters and `data/` are gitignored (generated artifacts).
