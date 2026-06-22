"""Smoke test for the Parkinson's detector (needs numpy/sklearn — run under the swechats venv,
NOT the zero-dep tests.test_core suite).

Run:  cd ~/mentat && PYTHONPATH=. ~/swechats/.venv/bin/python -m reference.parkinsons.test_detect
"""
from __future__ import annotations

from .detect import evaluate, load
from .final_model import predict
from .panel_search import subject_auc


def test_data_loads_and_groups_are_clean():
    X, y, groups, feats = load()
    assert len(y) == 195 and len(feats) == 22
    # no subject may carry both labels, else subject-level CV would be meaningless
    by_sub: dict = {}
    for g, yi in zip(groups, y):
        by_sub.setdefault(g, set()).add(int(yi))
    assert all(len(v) == 1 for v in by_sub.values()), "a subject has mixed labels"


def test_subject_level_beats_chance_and_below_leaky():
    X, y, groups, feats = load()
    honest = evaluate(X, y, groups, "hist_gb", subject_level=True)
    leaky = evaluate(X, y, groups, "hist_gb", subject_level=False)
    assert honest["auc_pooled"] > 0.65, "should clearly beat chance"
    assert leaky["auc_pooled"] > honest["auc_pooled"], "record-level leakage must inflate AUC"


def test_panel_selection_helps():
    X, y, groups, feats = load()
    Xv = X.to_numpy()
    full = subject_auc(Xv, y, groups, list(range(len(feats))), seeds=(0, 1, 2))
    panel = subject_auc(Xv, y, groups, [feats.index(f) for f in ["spread1", "MDVP:Fhi(Hz)", "D2"]],
                        seeds=(0, 1, 2))
    assert panel >= full, "the selected panel should not underperform the full (overfit) set"
    assert panel > 0.85, "selected panel should be a strong subject-level detector"


def test_predict_returns_probability():
    X, _, _, _ = load()
    r = predict(X.iloc[0].to_dict())
    assert 0.0 <= r["p_parkinsons"] <= 1.0
    assert r["prediction"] in ("Parkinson's", "healthy")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
