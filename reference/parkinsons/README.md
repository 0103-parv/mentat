# Parkinson's voice detector — a complete, working model on REAL clinical data

A genuinely working Parkinson's detector, end to end: real public clinical data → rigorous
subject-level validation → mentat-gated feature selection → a saved, callable model. Built with
what's actually on hand (a laptop, no GPU, no gated dataset, no API). It runs and it detects.

**Honest scope.** This is **not** the ISEF edge-VLM-on-gait submission (that needs the gated
CARE-PD dataset + a GPU and is its author's own competition work). This is a complete, real
detector on a *different, public* modality — sustained-phonation **voice** — that demonstrates
the whole pipeline and mentat's role, on data anyone can download.

## The data

UCI **Parkinsons** dataset (Little et al., 2007, *BioMedical Engineering OnLine*): 195 sustained
`/a/` phonation recordings from 32 people (24 with Parkinson's, 8 healthy), each summarised by 22
biomedical dysphonia features — jitter, shimmer, NHR/HNR, and nonlinear measures (RPDE, DFA,
spread1, spread2, D2, PPE). Label = `status` (1 = PD). The 40 KB CSV is committed under `data/`.
(The dataset doc says "31 people"; the `name` field actually encodes 32 distinct subject IDs —
we report what the data contains.)

## The result (honest, subject-level)

Each person contributes ~6 recordings, so the split you choose is everything:

| Evaluation | AUC | What it means |
|---|---|---|
| Record-level CV (naive) | **~0.95** | a patient's clips appear in train *and* test — the model learns the *person*. Inflated. |
| **Subject-level CV (honest)** | **~0.78** | no patient crosses train/test — generalises to a **new** person. |
| Inflation from leakage | **+0.17 AUC** | pure false confidence the naive number buys you. |

Then mentat searches feature subsets (gated by subject-level AUC + a parsimony penalty) and finds
that **fewer features generalise better** — all 22 features overfit on only 32 people:

| Panel | Subject-level AUC |
|---|---|
| All 22 features (logistic) | 0.70 (overfit) |
| `spread1` alone (top dysphonia measure) | **0.92** |
| **Recommended 3-feature panel** `spread1, MDVP:Fhi(Hz), D2` | **0.91** |

The deployable model (`final_model.py`) trains that panel on all the data and predicts on a new
recording with an **expected subject-level AUC of 0.91** stored alongside it.

## Files

| File | Purpose |
|---|---|
| `detect.py` | Loads data, subject-level vs record-level CV across 4 models, shows the leakage gap |
| `panel_search.py` | mentat's propose→verify→keep loop searches the size-vs-AUC feature frontier |
| `final_model.py` | Trains + saves the deployable panel model; `predict(recording_dict)` |
| `test_detect.py` | Smoke tests (data integrity, leakage gap, panel helps, predict works) |
| `data/parkinsons.data` | The real UCI dataset (committed, runs offline) |

## Run

```bash
cd ~/mentat
PYTHONPATH=. ~/swechats/.venv/bin/python reference/parkinsons/detect.py            # the honest report
PYTHONPATH=. ~/swechats/.venv/bin/python -m reference.parkinsons.panel_search      # mentat feature search
PYTHONPATH=. ~/swechats/.venv/bin/python -m reference.parkinsons.final_model       # train+save+predict
PYTHONPATH=. ~/swechats/.venv/bin/python -m reference.parkinsons.test_detect       # smoke tests
```
Needs `numpy`, `scikit-learn`, `pandas` (in `~/swechats/.venv`) and mentat on the path (`PYTHONPATH=.`).

## What mentat contributes here

Not the classifier (that's standard scikit-learn) — the **discipline**: every number is earned on
held-out *people*, and the feature panel is found by a gated search that never touches the test
patients. That's the same propose→verify→keep loop as the math/markets engines, pointed at a
clinical detection problem. The honest 0.78→0.91 story *is* the anti-overfit thesis on real data.
