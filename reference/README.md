# reference/ — Parkinson's gait-detection methods (study scaffold, NOT the ISEF submission)

These are **runnable methods references** that show where mentat's verification-gated kernel fits
the gait-based Parkinson's detection task. They run on **synthetic data** with literature-based PD
gait signatures — there is no GPU, no CARE-PD access, and no API here, so the actual edge
vision-language model is **not** trained in this folder.

**This is explicitly not the competition entry.** The ISEF project (the CARE-PD edge-VLM with
LieQ quantization + STTP token pruning) is the author's own work and stays theirs. This folder is
for studying the *methods* and seeing mentat's role, on synthetic stand-ins you can replace with
real features.

## ⭐ The complete working model: `parkinsons/` (REAL data)

**[`parkinsons/`](parkinsons/README.md)** is a complete, genuinely working Parkinson's detector on
**real public clinical data** (UCI voice dataset, 195 recordings / 32 people) — not synthetic.
Honest subject-level validation (AUC ~0.78, vs the leaky record-level ~0.95), mentat-gated feature
selection (a 3-feature panel reaches **AUC 0.91**, beating all 22 features), and a saved, callable
model (`predict(recording_dict)`). 4 smoke tests pass. This is the real deliverable; the two files
below are the earlier **synthetic-gait** illustrations of the same ideas.

```bash
cd ~/mentat && PYTHONPATH=. ~/swechats/.venv/bin/python reference/parkinsons/detect.py
```

## Synthetic-gait illustrations

| File | What it does | Verified result |
|------|--------------|-----------------|
| `parkinsons_detect.py` | Logistic-regression *synthetic-gait* detector + mentat minimal-panel search | full panel **85% acc / AUC 0.918**; mentat finds a **2-feature panel at AUC 0.889** |
| `gait_quant_policy.py` | mentat searches a mixed-precision bit-width policy (the LieQ idea) under a hard memory+accuracy gate | **verified** policy: 30% of FP16 memory, 90.3% acc, attention/head→8-bit, MLP→2-4bit |

Everything is judged on **held-out folds** (detector) or a **hard constraint verifier** (quant) —
nothing is believed unless it generalizes / provably meets the budget. That anti-overfit discipline
is the mentat contribution; the rest is standard, reusable methods code.

## Run

```bash
cd ~/mentat
PYTHONPATH=. ~/swechats/.venv/bin/python reference/parkinsons_detect.py    # detector + panel search
PYTHONPATH=. ~/swechats/.venv/bin/python reference/gait_quant_policy.py    # mixed-precision search
```
(Needs numpy — present in the `~/swechats/.venv`. The quant search needs no numpy.)

## To make it real (what you'd swap in)

- **Real features:** replace `synthesize()` in `parkinsons_detect.py` with gait features extracted
  from CARE-PD pose/SMPL meshes (stride time, cadence, asymmetry, arm swing, FOG index). The
  detector + held-out gate + panel search are unchanged.
- **Real quant verifier:** replace the synthetic per-layer sensitivity table in
  `gait_quant_policy.py` with the actual VLM evaluated on CARE-PD. The same gated search runs and
  returns a bit-width policy that provably meets your on-device budget.
- **STTP pruning** (Fiedler-vector token pruning) slots in as a third reference the same way — a
  spectral-centrality token selector judged by a "preserve body-region tokens" verifier.
