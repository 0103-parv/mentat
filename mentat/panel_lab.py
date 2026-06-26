"""Cross-sectional panel market for the false-alpha study (Task 2).

A single price series only supports time-series momentum/reversion, and close-only data
darkens the range/volume features. A PANEL of assets turns the whole DSL on and creates a
setting where a *moderate* cross-sectional edge plausibly exists — the strongest test of
whether the gate can find real edge in the wild.

The design keeps the GATE IDENTICAL. A DSL alpha is evaluated per asset into a score; at
each bar the scores are cross-sectionally demeaned and gross-normalized into a
dollar-neutral, unit-gross weight vector (the cross-sectional "rank"); the strategy's
per-bar return is the long-short portfolio return after turnover cost. That single return
series is then fed to the *same* worst-of-regimes, deflated-Sharpe gate as the single-index
engine — so survivors on a panel are produced by the unchanged validation, not a relaxed one.

  python3 -m mentat.panel_lab          # smoke: synthetic planted/noise panel + a sweep
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .trade_lab import Bars, _LCG, compute_features, eval_alpha, valid_alpha

PERIODS_PER_YEAR = 252
_ANN = math.sqrt(PERIODS_PER_YEAR)


# --------------------------------------------------------------------------- #
# panel data structure                                                        #
# --------------------------------------------------------------------------- #
@dataclass
class Panel:
    """A cross-section of `A` assets over `T` aligned bars. `bars[i]` is the single-asset
    Bars for asset i (so per-asset features reuse trade_lab.compute_features unchanged).
    `regimes` is the shared (label,start,end) timeline used for worst-regime scoring."""
    names: list[str]
    bars: list[Bars]
    regimes: list[tuple[str, int, int]]
    T: int
    _feat_cache: list = field(default=None, repr=False)

    def features(self):
        if self._feat_cache is None:
            self._feat_cache = [compute_features(b) for b in self.bars]
        return self._feat_cache


# --------------------------------------------------------------------------- #
# cross-sectional portfolio construction (the "rank")                         #
# --------------------------------------------------------------------------- #
def panel_portfolio(expr, panel: Panel, cost: float) -> tuple[list[float], list[float]] | None:
    """Per-bar long-short portfolio return + turnover for a DSL alpha. Weights are the
    cross-sectionally demeaned score, gross-normalized to unit exposure (dollar-neutral).
    Returns None if the alpha never trades (no cross-sectional dispersion)."""
    feats = panel.features()
    A, T = len(panel.bars), panel.T
    scores = [eval_alpha(expr, feats[i]) for i in range(A)]      # per-asset score series
    # weights[t] = demeaned, gross-normalized score across assets at bar t
    W = [[0.0] * A for _ in range(T)]
    for t in range(T):
        row = [scores[i][t] for i in range(A)]
        m = sum(row) / A
        dev = [x - m for x in row]
        gross = sum(abs(x) for x in dev)
        if gross > 1e-12:
            for i in range(A):
                W[t][i] = dev[i] / gross                          # sum|w|=1, sum w=0
    # next-bar portfolio return, minus turnover cost
    port, turn = [0.0] * T, [0.0] * T
    rets = [panel.bars[i].ret for i in range(A)]
    for t in range(2, T):
        pr = sum(W[t - 1][i] * rets[i][t] for i in range(A))
        tv = sum(abs(W[t - 1][i] - W[t - 2][i]) for i in range(A))
        port[t] = pr - cost * tv
        turn[t] = tv
    if sum(turn) / max(T, 1) < 1e-9:
        return None
    return port, turn


def _seg_sharpe(series: list[float], s: int, e: int) -> tuple[float, int]:
    seg = [series[t] for t in range(max(s, 2), e)]
    if len(seg) < 2:
        return 0.0, len(seg)
    m = sum(seg) / len(seg)
    var = sum((x - m) ** 2 for x in seg) / (len(seg) - 1)
    return (m / math.sqrt(var) if var > 1e-18 else 0.0), len(seg)


def panel_backtest_raw(expr, panel: Panel, cost: float) -> dict | None:
    """Same shape/contract as nsweep.backtest_raw, computed on the long-short portfolio
    return series. The gate downstream is byte-identical to the single-index path."""
    if not valid_alpha(expr):
        return None
    pt = panel_portfolio(expr, panel, cost)
    if pt is None:
        return None
    port, turn = pt
    is_seg = next((r for r in panel.regimes if r[0].startswith("is")), panel.regimes[0])
    oos = [r for r in panel.regimes if not r[0].startswith("is")]
    if not oos:
        return None
    worst, worst_n, worst_lbl = None, 0, "none"
    for label, s, e in oos:
        sh, n = _seg_sharpe(port, s, e)
        if worst is None or sh < worst:
            worst, worst_n, worst_lbl = sh, n, label
    pooled_sh, _ = _seg_sharpe(port, oos[0][1], oos[-1][2])
    is_sh, _ = _seg_sharpe(port, is_seg[1], is_seg[2])
    oos_turn = [turn[t] for _, s, e in oos for t in range(max(s, 2), e)]
    avg_turn = sum(oos_turn) / len(oos_turn) if oos_turn else 0.0
    return {
        "naive_per_bar": pooled_sh, "naive_n": worst_n, "naive_ann": pooled_sh * _ANN,
        "worst_per_bar": worst, "worst_n": worst_n, "worst_ann": worst * _ANN,
        "is_ann": is_sh * _ANN, "turnover": avg_turn, "worst_regime": worst_lbl,
    }


def panel_oos_returns(expr, panel: Panel, cost: float) -> list[float]:
    """Per-bar OOS portfolio return series (for correlation / bootstrap), matching
    nsweep.oos_strat_returns' contract."""
    pt = panel_portfolio(expr, panel, cost)
    if pt is None:
        return []
    port = pt[0]
    oos = [r for r in panel.regimes if not r[0].startswith("is")]
    if not oos:
        return []
    s, e = oos[0][1], oos[-1][2]
    return [port[t] for t in range(max(s, 2), e)]


# --------------------------------------------------------------------------- #
# synthetic cross-sectional markets (planted reversal edge + null twin)       #
# --------------------------------------------------------------------------- #
def synthetic_panel(cs_reversal: float, *, n_assets: int = 15, seed: int = 3) -> Panel:
    """A panel with a CROSS-SECTIONAL lag-1 reversal edge of strength `cs_reversal`
    (assets that beat the cross-section last bar revert next bar — the same sign in every
    regime, so a cross-sectional reversal alpha generalises). cs_reversal=0 is the pure
    cross-sectional null. A market factor + idiosyncratic noise + OHLCV (so range/volume
    features are active) round out the panel."""
    rng = _LCG(seed)
    plan = [("is_train", 750, 0.0004, 0.008, 0.012),
            ("oos_bull", 500, 0.0006, 0.006, 0.010),
            ("oos_bear", 500, -0.0005, 0.013, 0.018),
            ("oos_chop", 500, 0.0000, 0.009, 0.014)]
    A = n_assets
    closes = [[100.0] for _ in range(A)]
    highs, lows, vols, rets = [[] for _ in range(A)], [[] for _ in range(A)], \
        [[] for _ in range(A)], [[] for _ in range(A)]
    prev_rel = [0.0] * A
    regimes, idx = [], 0
    price = [100.0] * A
    for label, n_bars, drift, mkt_vol, idio_vol in plan:
        start = idx
        for _ in range(n_bars):
            mkt = rng.gauss() * mkt_vol
            raw = []
            for i in range(A):
                r = drift + mkt - cs_reversal * prev_rel[i] + rng.gauss() * idio_vol
                raw.append(r)
            mean_r = sum(raw) / A
            for i in range(A):
                r = raw[i]
                prev_rel[i] = r - mean_r                  # this bar's relative return -> next bar
                new_p = max(1e-3, price[i] * (1.0 + r))
                realized = new_p / price[i] - 1.0
                intra = abs(rng.gauss()) * idio_vol * new_p
                highs[i].append(max(price[i], new_p) + 0.5 * intra)
                lows[i].append(max(1e-3, min(price[i], new_p) - 0.5 * intra))
                vols[i].append(1_000_000.0 * (1.0 + 0.3 * abs(rng.gauss())))
                rets[i].append(realized)
                if idx > 0:
                    closes[i].append(new_p)
                price[i] = new_p
            idx += 1
        regimes.append((label, start, idx))
    bars = []
    for i in range(A):
        c = closes[i] if len(closes[i]) == idx else closes[i][:idx]
        bars.append(Bars(c, highs[i], lows[i], vols[i], rets[i], list(regimes)))
    return Panel([f"S{i}" for i in range(A)], bars, regimes, idx)


def _bars_from_series(close, high, low, volume, n_oos=3, is_frac=0.4) -> Bars:
    n = len(close)
    ret = [0.0] + [close[t] / close[t - 1] - 1.0 for t in range(1, n)]
    is_end = max(2, int(n * is_frac))
    regimes = [("is_train", 0, is_end)]
    rem = n - is_end
    step = max(1, rem // max(1, n_oos))
    for i in range(n_oos):
        s = is_end + i * step
        e = n if i == n_oos - 1 else min(n, is_end + (i + 1) * step)
        if s < e:
            regimes.append((f"oos_{i + 1}", s, e))
    return Bars(close, high, low, volume, ret, regimes)


def load_panel_csv(path, *, n_oos_regimes: int = 3, is_frac: float = 0.4) -> Panel:
    """Build a real Panel from a wide CSV: date,<TICK1>_close,<TICK1>_high,... one row per
    date. Produced by fetch_panel.py from real OHLCV. Assets are aligned on common dates."""
    import csv
    from pathlib import Path
    rows = list(csv.reader(Path(path).read_text().splitlines()))
    header = rows[0]
    cols = {h: i for i, h in enumerate(header)}
    tickers = sorted({h.rsplit("_", 1)[0] for h in header if "_close" in h})
    series = {tk: {"close": [], "high": [], "low": [], "volume": []} for tk in tickers}
    for r in rows[1:]:
        ok = all(r[cols[f"{tk}_close"]] not in ("", ".") for tk in tickers)
        if not ok:
            continue
        for tk in tickers:
            series[tk]["close"].append(float(r[cols[f"{tk}_close"]]))
            series[tk]["high"].append(float(r[cols.get(f"{tk}_high", cols[f"{tk}_close"])]))
            series[tk]["low"].append(float(r[cols.get(f"{tk}_low", cols[f"{tk}_close"])]))
            series[tk]["volume"].append(float(r[cols.get(f"{tk}_volume", -1)] or 1.0)
                                        if f"{tk}_volume" in cols else 1.0)
    T = len(series[tickers[0]]["close"])
    if T < 100:
        raise ValueError(f"{path}: too few aligned rows ({T})")
    bars = [_bars_from_series(series[tk]["close"], series[tk]["high"], series[tk]["low"],
                              series[tk]["volume"], n_oos_regimes, is_frac) for tk in tickers]
    return Panel(list(tickers), bars, bars[0].regimes, T)


def main() -> int:
    from .nsweep import deflated_ann
    print("PANEL SMOKE — cross-sectional planted reversal vs null (gate unchanged)\n")
    from .imagine import CreativeProposer  # noqa: F401
    import random
    from .nsweep import random_alpha
    for label, panel in [("cs_planted", synthetic_panel(0.35)),
                         ("cs_small", synthetic_panel(0.05)),
                         ("cs_noise", synthetic_panel(0.0))]:
        rng = random.Random(1)
        best, surv = -9.9, 0
        feats = panel.features()
        active = sum(1 for f in feats for k in ("hl_range", "volume_z")
                     if any(abs(v) > 1e-9 for v in f[k][:50]))
        for _ in range(400):
            a = random_alpha(rng)
            r = panel_backtest_raw(a, panel, 0.001)
            if r:
                best = max(best, r["worst_ann"])
                if deflated_ann(r, 400) >= 0.5:
                    surv += 1
        print(f"  {label:11} best worst-OOS Sharpe={best:+.2f}  survivors@N=400={surv}  "
              f"(range/volume active cells={active})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
