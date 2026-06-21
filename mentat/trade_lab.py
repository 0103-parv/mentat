"""Alpha discovery for the Mentat kernel — the anti-overfit trading flagship.

The reasoning core proposes an ALPHA as a formula in a small DSL over price/volume
features (mirroring alpha-evolver's S-expression programs). The verifier is a
BRUTAL backtest, not a friendly one:

  1. EVALUATE the alpha causally (each bar uses only past data) into a signal,
     then a position, traded on the NEXT bar (no look-ahead).
  2. Charge realistic TRANSACTION COSTS on every position change.
  3. Score it OUT-OF-SAMPLE across >= 2 market REGIMES and take the WORST regime
     (an alpha must generalise to survive — one good regime is not enough).
  4. Apply a DEFLATED-SHARPE / multiple-testing penalty: you searched N alphas, so
     discount the best by the Sharpe a lucky null strategy would reach over N tries
     (Bailey & Lopez de Prado, 2014). This is what kills overfit.

The thesis (VISION.md): *verification IS the anti-overfit mechanism.* Naive alpha
search keeps what looked good in-sample and dies live. An alpha only enters the
verified library here if its WORST-regime, after-cost, deflated OOS Sharpe clears a
positive bar. Brittle, churny, or in-sample-only alphas are quarantined by the
kernel's existing suspicious/quarantine path.

Pure Python, no numpy — same as math_lab.py — so it runs and tests anywhere.

Run:  python3 -m mentat.trade     (a reasoning core is optional; offline fallback works)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist

from .core import Lesson, Memory, Mind, Problem, Verdict

PERIODS_PER_YEAR = 252          # treat each bar as a trading day
EULER = 0.5772156649015329      # Euler-Mascheroni, for the expected-max-Sharpe term
_NORM = NormalDist()

# --------------------------------------------------------------------------- #
# the alpha DSL                                                               #
# --------------------------------------------------------------------------- #
# An <expr> is a feature name (str), a constant name (str), or [op, arg, ...].
# Leaves are per-bar feature arrays; ops combine them element-wise. The signal an
# expr produces becomes a target position in [-1, 1] (clipped) on the next bar.

# Causal features the alpha may read (all computed from data up to the current bar).
FEATURES = (
    "ret1",            # last bar's simple return
    "mom5", "mom10", "mom20",   # cumulative return over the trailing window
    "vol10", "vol20",  # rolling stdev of returns (trailing)
    "accel",           # mom5 - mom10 (momentum acceleration)
    "price_ma_gap",    # close / SMA20 - 1 (stretch above/below the trend)
    "hl_range",        # (high - low) / close (intrabar range)
    "volume_z",        # z-scored volume over a trailing window (often a decoy)
)
CONSTANTS = {
    "c_neg1": -1.0, "c_neg05": -0.5, "c_0": 0.0,
    "c_05": 0.5, "c_1": 1.0, "c_2": 2.0,
}
_UNARY = {"neg", "abs", "sign", "tanh", "zscore"}
_BINARY = {"add", "sub", "mul", "safe_div", "min", "max"}

# Each feature's signal FAMILY — the illumination niche, so the agent keeps the best
# robust alpha of each kind (a diverse family of signals).
_FEATURE_FAMILY = {
    "ret1": "reversion", "accel": "reversion",
    "mom5": "momentum", "mom10": "momentum", "mom20": "momentum",
    "vol10": "volatility", "vol20": "volatility",
    "volume_z": "volume", "price_ma_gap": "trend", "hl_range": "range",
}


def _feature_leaves(expr) -> list[str]:
    if isinstance(expr, str):
        return [expr] if expr in FEATURES else []
    if isinstance(expr, (list, tuple)) and expr:
        out: list[str] = []
        for a in expr[1:]:
            out.extend(_feature_leaves(a))
        return out
    return []
_ZSCORE_WINDOW = 20
_MAX_DEPTH = 5
_MAX_SIZE = 40


def valid_alpha(expr, _depth: int = 1) -> bool:
    """Grammar + depth/size guard. The verifier rejects anything off-grammar."""
    if _depth > _MAX_DEPTH or _expr_size(expr) > _MAX_SIZE:
        return False
    return _valid(expr, _depth)


def _valid(expr, depth: int) -> bool:
    if depth > _MAX_DEPTH:
        return False
    if isinstance(expr, str):
        return expr in FEATURES or expr in CONSTANTS
    if isinstance(expr, (list, tuple)) and expr:
        op, args = expr[0], list(expr[1:])
        if op in _UNARY:
            return len(args) == 1 and _valid(args[0], depth + 1)
        if op in _BINARY:
            return len(args) == 2 and all(_valid(a, depth + 1) for a in args)
    return False


def _expr_size(expr) -> int:
    if isinstance(expr, str):
        return 1
    if isinstance(expr, (list, tuple)) and expr:
        return 1 + sum(_expr_size(a) for a in expr[1:])
    return 1


def expr_to_str(expr) -> str:
    if isinstance(expr, str):
        return expr
    if isinstance(expr, (list, tuple)) and expr:
        return f"{expr[0]}(" + ", ".join(expr_to_str(a) for a in expr[1:]) + ")"
    return str(expr)


# --------------------------------------------------------------------------- #
# evaluating an alpha into a per-bar signal                                   #
# --------------------------------------------------------------------------- #
def _rolling_zscore(xs: list[float], window: int) -> list[float]:
    """Causal z-score over the trailing `window` bars (0 until enough history)."""
    out = [0.0] * len(xs)
    for t in range(len(xs)):
        lo = max(0, t - window + 1)
        win = xs[lo:t + 1]
        if len(win) < 2:
            continue
        m = sum(win) / len(win)
        var = sum((w - m) ** 2 for w in win) / (len(win) - 1)
        sd = math.sqrt(var)
        out[t] = (xs[t] - m) / sd if sd > 1e-12 else 0.0
    return out


def eval_alpha(expr, feats: dict[str, list[float]]) -> list[float]:
    """Evaluate an expr to a per-bar signal array. Non-finite results are zeroed
    so a single bad bar cannot poison the whole backtest."""
    n = len(next(iter(feats.values())))
    if isinstance(expr, str):
        if expr in feats:
            col = feats[expr]
        elif expr in CONSTANTS:
            col = [CONSTANTS[expr]] * n
        else:
            raise ValueError(f"unknown leaf: {expr!r}")
        return [v if math.isfinite(v) else 0.0 for v in col]

    if not (isinstance(expr, (list, tuple)) and expr):
        raise ValueError(f"malformed expr: {expr!r}")
    op = expr[0]
    if op in _UNARY:
        a = eval_alpha(expr[1], feats)
        if op == "neg":
            out = [-x for x in a]
        elif op == "abs":
            out = [abs(x) for x in a]
        elif op == "sign":
            out = [(x > 0) - (x < 0) for x in a]
        elif op == "tanh":
            out = [math.tanh(x) for x in a]
        elif op == "zscore":
            out = _rolling_zscore(a, _ZSCORE_WINDOW)
        return [v if math.isfinite(v) else 0.0 for v in out]
    if op in _BINARY:
        a = eval_alpha(expr[1], feats)
        b = eval_alpha(expr[2], feats)
        if op == "add":
            out = [x + y for x, y in zip(a, b)]
        elif op == "sub":
            out = [x - y for x, y in zip(a, b)]
        elif op == "mul":
            out = [x * y for x, y in zip(a, b)]
        elif op == "safe_div":
            out = [x / y if abs(y) > 1e-9 else 0.0 for x, y in zip(a, b)]
        elif op == "min":
            out = [min(x, y) for x, y in zip(a, b)]
        elif op == "max":
            out = [max(x, y) for x, y in zip(a, b)]
        return [v if math.isfinite(v) else 0.0 for v in out]
    raise ValueError(f"unknown op: {op!r}")


# --------------------------------------------------------------------------- #
# market data: features + a synthetic multi-regime universe                   #
# --------------------------------------------------------------------------- #
@dataclass
class Bars:
    """OHLCV plus per-bar simple returns. `regimes` marks contiguous segments
    [(label, start, end)] used to score worst-regime OOS performance."""
    close: list[float]
    high: list[float]
    low: list[float]
    volume: list[float]
    ret: list[float]
    regimes: list[tuple[str, int, int]] = field(default_factory=list)


def compute_features(bars: Bars) -> dict[str, list[float]]:
    """Build the causal feature columns the DSL reads. Every value at bar t uses
    only information available through bar t (returns through t).

    Cached on the Bars instance: features depend ONLY on the bars, not on the alpha, so
    they are computed once per universe instead of once per alpha evaluation — the
    dominant cost of every market engine (profiled at ~85% of runtime)."""
    cached = getattr(bars, "_feature_cache", None)
    if cached is not None:
        return cached
    c, hi, lo, vol, r = bars.close, bars.high, bars.low, bars.volume, bars.ret
    n = len(c)

    def momentum(window: int) -> list[float]:
        out = [0.0] * n
        for t in range(n):
            lo_i = max(0, t - window + 1)
            out[t] = sum(r[lo_i:t + 1])
        return out

    def rolling_vol(window: int) -> list[float]:
        out = [0.0] * n
        for t in range(n):
            lo_i = max(0, t - window + 1)
            win = r[lo_i:t + 1]
            if len(win) < 2:
                continue
            m = sum(win) / len(win)
            out[t] = math.sqrt(sum((w - m) ** 2 for w in win) / (len(win) - 1))
        return out

    def sma(window: int) -> list[float]:
        out = [0.0] * n
        for t in range(n):
            lo_i = max(0, t - window + 1)
            win = c[lo_i:t + 1]
            out[t] = sum(win) / len(win)
        return out

    mom5, mom10, mom20 = momentum(5), momentum(10), momentum(20)
    vol10, vol20 = rolling_vol(10), rolling_vol(20)
    ma20 = sma(20)
    feats = {
        "ret1": list(r),
        "mom5": mom5,
        "mom10": mom10,
        "mom20": mom20,
        "vol10": vol10,
        "vol20": vol20,
        "accel": [a - b for a, b in zip(mom5, mom10)],
        "price_ma_gap": [c[t] / ma20[t] - 1.0 if ma20[t] > 1e-9 else 0.0 for t in range(n)],
        "hl_range": [(hi[t] - lo[t]) / c[t] if c[t] > 1e-9 else 0.0 for t in range(n)],
        "volume_z": _rolling_zscore(vol, _ZSCORE_WINDOW),
    }
    try:
        bars._feature_cache = feats          # Bars is a plain dataclass (not frozen)
    except Exception:
        pass
    return feats


class _LCG:
    """Tiny deterministic PRNG (no numpy dep). Gaussian via Box-Muller."""
    def __init__(self, seed: int):
        self.s = seed & 0xFFFFFFFF or 1

    def _u(self) -> float:
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s / 0x7FFFFFFF

    def gauss(self) -> float:
        u1 = max(self._u(), 1e-12)
        u2 = self._u()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def synthetic_universe(seed: int = 7) -> Bars:
    """A deterministic OHLCV series with a SMALL, REAL, regime-consistent edge plus
    decoys — the honest testbed for the anti-overfit gate.

    The edge: lag-1 mean reversion (next return leans against the last return). It
    is the SAME sign in every regime, so a mean-reversion alpha generalises and
    survives the worst-regime gate. Regimes differ in drift and volatility, so
    alphas that lean on drift (always-long, raw momentum) win in one regime and
    lose in another -> killed by worst-regime + cost + deflation. Volume carries no
    edge (a decoy), so volume-based alphas should not survive.
    """
    rng = _LCG(seed)
    # (label, n_bars, drift_per_bar, vol_per_bar)
    plan = [
        ("is_train", 750, 0.0004, 0.010),
        ("oos_bull", 500, 0.0006, 0.008),
        ("oos_bear", 500, -0.0005, 0.016),
        ("oos_chop", 500, 0.0000, 0.012),
    ]
    reversion = 0.40                      # strength of the lag-1 mean reversion (the edge)
    close, high, low, volume, ret = [], [], [], [], []
    regimes: list[tuple[str, int, int]] = []
    price = 100.0
    prev_r = 0.0
    idx = 0
    for label, n_bars, drift, vol in plan:
        start = idx
        for _ in range(n_bars):
            shock = rng.gauss() * vol
            r = drift - reversion * prev_r + shock     # the embedded edge
            prev_r = r
            new_price = max(1e-3, price * (1.0 + r))
            realized = new_price / price - 1.0
            intrabar = abs(rng.gauss()) * vol * new_price
            hi = max(price, new_price) + 0.5 * intrabar
            lo = min(price, new_price) - 0.5 * intrabar
            v = 1_000_000.0 * (1.0 + 0.3 * abs(rng.gauss()))   # decoy volume
            close.append(new_price)
            high.append(hi)
            low.append(max(1e-3, lo))
            volume.append(v)
            ret.append(realized)
            price = new_price
            idx += 1
        regimes.append((label, start, idx))
    return Bars(close, high, low, volume, ret, regimes)


def _bars_with_auto_regimes(close, high, low, volume, ret, n_oos: int, is_frac: float) -> Bars:
    """IS = first `is_frac` of the timeline; the rest split into `n_oos` equal
    contiguous OOS eras. Equal contiguous chunks (not hand-picked dates) keep the
    regime split honest — different market environments fall out on their own."""
    n = len(close)
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


def load_price_csv(path, *, n_oos_regimes: int = 3, is_frac: float = 0.4) -> Bars:
    """Build Bars from a real price CSV. Accepts a generic OHLCV header
    (date,open,high,low,close,volume — Stooq/Yahoo style) or a 2-column
    date,value series (FRED style). Missing/holiday rows ('.' or blank) are
    dropped. Close-only series get high=low=close and volume=1 (so hl_range and
    the volume decoy go dark, while every return-based feature still works)."""
    from pathlib import Path
    lines = [ln for ln in Path(path).read_text().splitlines() if ln.strip()]
    if len(lines) < 50:
        raise ValueError(f"{path}: too few rows ({len(lines)}) for a backtest")
    header = [h.strip().lower() for h in lines[0].split(",")]
    if "close" in header:
        ci = header.index("close")
        hi = header.index("high") if "high" in header else None
        li = header.index("low") if "low" in header else None
        vi = header.index("volume") if "volume" in header else None
    else:
        ci, hi, li, vi = 1, None, None, None        # FRED date,value

    def num(parts, i, default):
        if i is None or i >= len(parts):
            return default
        raw = parts[i].strip()
        if raw in ("", "."):
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    close, high, low, volume = [], [], [], []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) <= ci:
            continue
        c = num(parts, ci, None)
        if c is None or c <= 0:
            continue
        close.append(c)
        high.append(num(parts, hi, c))
        low.append(num(parts, li, c))
        volume.append(num(parts, vi, 1.0))
    if len(close) < 50:
        raise ValueError(f"{path}: too few valid price rows ({len(close)})")
    ret = [0.0] + [close[t] / close[t - 1] - 1.0 for t in range(1, len(close))]
    return _bars_with_auto_regimes(close, high, low, volume, ret, n_oos_regimes, is_frac)


# --------------------------------------------------------------------------- #
# the brutal backtest                                                         #
# --------------------------------------------------------------------------- #
def _positions(signal: list[float]) -> list[float]:
    """Map a raw signal to a target position in [-1, 1] (tanh-squash then clip)."""
    return [max(-1.0, min(1.0, math.tanh(s))) for s in signal]


def segment_metrics(
    positions: list[float], ret: list[float], start: int, end: int, cost: float
) -> dict[str, float]:
    """After-cost per-bar Sharpe + turnover over [start, end), traded next-bar.

    strat[t] = pos[t-1] * ret[t] - cost * |pos[t-1] - pos[t-2]|.  The position is
    formed on bar t-1's information and earns bar t's return, so there is no
    look-ahead. Returns Sharpe = 0 for a degenerate (never-trading) segment."""
    rs: list[float] = []
    turnover = 0.0
    for t in range(max(start, 2), end):
        prev, prev2 = positions[t - 1], positions[t - 2]
        trade = abs(prev - prev2)
        turnover += trade
        rs.append(prev * ret[t] - cost * trade)
    if len(rs) < 2:
        return {"sharpe": 0.0, "n": float(len(rs)), "turnover": 0.0, "mean": 0.0}
    m = sum(rs) / len(rs)
    var = sum((x - m) ** 2 for x in rs) / (len(rs) - 1)
    sd = math.sqrt(var)
    sharpe = m / sd if sd > 1e-12 else 0.0
    return {
        "sharpe": sharpe,                       # per-bar
        "n": float(len(rs)),
        "turnover": turnover / len(rs),         # avg position change per bar
        "mean": m,
    }


def expected_max_sharpe_under_null(n_trials: int, n_obs: int, sharpe: float) -> float:
    """Per-bar Sharpe a LUCKY null strategy is expected to reach as the best of
    `n_trials` independent searches (Bailey & Lopez de Prado, deflated Sharpe).

    var(SR_hat) ~ (1 + 0.5*SR^2)/T; the best of N standard searches sits at
    sqrt(var) * [(1-gamma)*Z^-1(1-1/N) + gamma*Z^-1(1-1/(N e))]. Subtracting this
    is the multiple-testing haircut: search more, and the bar to clear rises."""
    n = max(int(n_trials), 2)
    t = max(int(n_obs), 2)
    var_sr = (1.0 + 0.5 * sharpe * sharpe) / t
    z1 = _NORM.inv_cdf(1.0 - 1.0 / n)
    z2 = _NORM.inv_cdf(1.0 - 1.0 / (n * math.e))
    return math.sqrt(max(var_sr, 0.0)) * ((1.0 - EULER) * z1 + EULER * z2)


def walk_forward_backtest(
    expr, bars: Bars, *, cost: float = 0.0010, n_trials: int = 60
) -> dict[str, float]:
    """The verifier's core. Returns annualized, after-cost metrics:

      - is_sharpe        : in-sample (training segment) — for the overfit check only
      - worst_oos_sharpe : the WORST OOS regime's after-cost Sharpe (generalisation)
      - deflated_oos     : worst_oos_sharpe minus the multiple-testing haircut  <- SCORE
      - turnover         : avg OOS position change per bar (churn -> cost drag)
    """
    feats = compute_features(bars)
    signal = eval_alpha(expr, feats)
    pos = _positions(signal)
    ann = math.sqrt(PERIODS_PER_YEAR)

    is_seg = next((r for r in bars.regimes if r[0].startswith("is")), bars.regimes[0])
    oos_segs = [r for r in bars.regimes if not r[0].startswith("is")]
    if not oos_segs:                       # no held-out regimes -> nothing to trust
        return {"is_sharpe": 0.0, "worst_oos_sharpe": 0.0, "deflated_oos": 0.0,
                "turnover": 0.0, "n_oos_regimes": 0.0, "worst_regime": "none"}

    is_m = segment_metrics(pos, bars.ret, is_seg[1], is_seg[2], cost)
    worst = None
    worst_label = "none"
    turnovers = []
    for label, s, e in oos_segs:
        m = segment_metrics(pos, bars.ret, s, e, cost)
        turnovers.append(m["turnover"])
        if worst is None or m["sharpe"] < worst["sharpe"]:
            worst, worst_label = m, label

    haircut = expected_max_sharpe_under_null(n_trials, int(worst["n"]), worst["sharpe"])
    deflated_per_bar = worst["sharpe"] - haircut
    return {
        "is_sharpe": is_m["sharpe"] * ann,
        "worst_oos_sharpe": worst["sharpe"] * ann,
        "deflated_oos": deflated_per_bar * ann,
        "haircut": haircut * ann,
        "turnover": sum(turnovers) / len(turnovers),
        "n_oos_regimes": float(len(oos_segs)),
        "worst_regime": worst_label,
    }


# --------------------------------------------------------------------------- #
# the problem: the verifier IS the problem                                    #
# --------------------------------------------------------------------------- #
class AlphaProblem(Problem):
    name = "robust-alpha-discovery"

    def __init__(self, bars: Bars | None = None, *, target: float = 0.5,
                 cost: float = 0.0010, n_trials: int = 60):
        self.bars = bars or synthetic_universe()
        self.target = target            # annualized deflated worst-regime OOS Sharpe
        self.cost = cost
        self.n_trials = n_trials        # the multiple-testing N (fixed -> comparable)
        self.statement = (
            "discover a trading alpha whose worst-regime, after-cost, deflated "
            "out-of-sample Sharpe clears a positive bar")

    def brief(self) -> str:
        return (
            "Design a trading ALPHA as a JSON expression over price/volume features. "
            "It is scored OUT-OF-SAMPLE across several market regimes; your score is "
            "the WORST regime's after-cost Sharpe, minus a multiple-testing haircut "
            f"(deflated Sharpe). Beat {self.target:.2f} annualized to win.\n"
            "An <expr> is a feature name (string), a constant, or [op, arg, ...].\n"
            f"  features: {', '.join(FEATURES)}\n"
            f"  constants: {', '.join(CONSTANTS)}\n"
            "  unary  = neg abs sign tanh zscore   (zscore is a trailing 20-bar z)\n"
            "  binary = add sub mul safe_div min max\n"
            "  (expr depth <= 5, total size <= 40). The signal becomes a position in "
            "[-1,1] traded on the NEXT bar.\n"
            "SCORING REALITY: every position change pays a transaction cost, so churny "
            "alphas bleed out; an alpha that wins in one regime but loses in another "
            "scores by its WORST regime; and because many alphas are tried, the best is "
            "discounted (deflated). To win you need a SMALL, ROBUST edge that holds in "
            "every regime after costs — not a complex curve fit. Volume carries no edge.")

    def verify(self, candidate) -> Verdict:
        try:
            if not valid_alpha(candidate):
                return Verdict(False, -1e9, "off-grammar alpha (rejected by the verifier)",
                               suspicious=True)
            m = walk_forward_backtest(candidate, self.bars, cost=self.cost,
                                      n_trials=self.n_trials)
            deflated = m["deflated_oos"]
            if not math.isfinite(deflated):
                return Verdict(False, -1e9, "non-finite Sharpe", suspicious=True)
            if m["turnover"] < 1e-6:
                # never trades -> no information, not a real strategy
                return Verdict(False, -1e9, "degenerate alpha (never trades)", suspicious=True)
            # The overfit signature: great in-sample, loses money in the worst OOS regime.
            overfit = m["is_sharpe"] > 1.0 and m["worst_oos_sharpe"] < 0.0
            detail = (f"deflated OOS Sharpe={deflated:+.3f} "
                      f"(worst regime '{m['worst_regime']}' OOS={m['worst_oos_sharpe']:+.3f}, "
                      f"haircut={m['haircut']:.3f}, IS={m['is_sharpe']:+.3f}, "
                      f"turnover={m['turnover']:.3f}) alpha={expr_to_str(candidate)}")
            return Verdict(deflated >= self.target, float(deflated), detail, suspicious=overfit)
        except Exception as e:
            return Verdict(False, -1e9, f"rejected: {type(e).__name__}: {e}", suspicious=True)

    def solved(self, v: Verdict) -> bool:
        return v.passed

    def behavior(self, candidate):
        """Illumination niche = the alpha's SIGNAL FAMILY (cheap, structural — no
        backtest). Lets the kernel keep the best robust alpha of EACH kind, so the
        result is a diverse FAMILY of signals (reversion / momentum / volatility /
        trend / volume / range), not one. Returns None for off-grammar alphas."""
        if not valid_alpha(candidate):
            return None
        fams = [_FEATURE_FAMILY[f] for f in _feature_leaves(candidate)
                if f in _FEATURE_FAMILY]
        if not fams:
            return "constant"
        return max(sorted(set(fams)), key=fams.count)

    def stress_verify(self, candidate, verdict: Verdict) -> Verdict:
        """The safety half of productive surprise: re-backtest a suspiciously-good
        alpha under TRIPLED transaction costs. An edge that only survives at low
        cost is a fragile/overfit fit — it fails here and gets quarantined; a
        genuinely robust, low-turnover edge survives. (Codex's ablation showed this
        quarantine is the piece that consistently earns its keep.)"""
        try:
            harsh = max(self.cost * 1.5, self.cost + 0.0003)
            m = walk_forward_backtest(candidate, self.bars, cost=harsh, n_trials=self.n_trials)
            d = m["deflated_oos"]
            ok = math.isfinite(d) and d > 0.0 and m["worst_oos_sharpe"] > 0.0
            return Verdict(
                bool(ok and verdict.passed),
                float(d) if math.isfinite(d) else -1e9,
                f"stress(3x cost={harsh:.4f}) deflated OOS={d:+.3f}; {verdict.detail}",
                suspicious=not ok,
            )
        except Exception as e:
            return Verdict(False, -1e9, f"stress rejected: {type(e).__name__}: {e}",
                           suspicious=True)

    def distill(self, best_candidate, best_verdict) -> list[Lesson]:
        if best_candidate is None or best_verdict is None or not best_verdict.detail:
            return []
        if not best_verdict.passed:      # only learn from an alpha that truly cleared the gate
            return []
        return [Lesson(
            when="building a trading alpha that must survive out-of-sample across regimes",
            do="reuse the verified deflated-Sharpe alpha that held up after costs",
            avoid="curve-fit alphas strong in-sample but negative in the worst OOS regime",
            evidence=best_verdict.detail)]


# --------------------------------------------------------------------------- #
# baseline alphas (offline fallback + something to evolve from)               #
# --------------------------------------------------------------------------- #
# The discoverable winner is mean reversion (#1/#2): it leans against the edge in
# every regime. Momentum/breakout (#3/#5) win in the trending regime but lose in
# another -> killed by worst-regime + cost + deflation. Good honest testbed.
BASELINE_ALPHAS = [
    ["neg", "ret1"],                                          # lag-1 mean reversion
    ["neg", ["zscore", "ret1"]],                              # normalized mean reversion
    "mom20",                                                  # momentum (regime-fragile)
    ["safe_div", "mom20", "vol20"],                           # vol-scaled momentum
    ["sign", "price_ma_gap"],                                 # trend breakout
    ["sub", ["neg", "ret1"], ["mul", "c_05", "mom5"]],        # reversion minus short momentum
]


def normalize_alpha(expr):
    """Best-effort coercion of a proposed alpha to the grammar. Lists/strings pass
    through; tuples become lists; anything invalid is left for valid_alpha to reject."""
    if isinstance(expr, str):
        return expr
    if isinstance(expr, (list, tuple)) and expr:
        return [expr[0]] + [normalize_alpha(a) for a in expr[1:]]
    return expr


def _extract_alphas(text: str) -> list:
    """Pull a JSON array of alpha expressions from a model reply (tolerant of
    ```json fences and leading/trailing prose)."""
    import json
    import re
    stripped = re.sub(r"```(?:json)?", "", text).strip().strip("`").strip()
    for cand in (stripped, text):
        try:
            v = json.loads(cand)
            if isinstance(v, list) and v:
                return v
        except Exception:
            pass
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    v = json.loads(text[start:i + 1])
                    if isinstance(v, list) and v:
                        return v
                except Exception:
                    pass
                start = None
    return []


@dataclass
class AlphaProposer:
    """The reasoning core proposing alphas. Each is verified by the brutal backtest;
    any shortfall is filled with baseline alphas so the loop never starves (and runs
    offline in tests)."""
    core: object
    fallback: list = field(default_factory=lambda: list(BASELINE_ALPHAS))
    last: list = field(default_factory=list)
    note: str = ""

    _SYSTEM = (
        "You are the reasoning core of an anti-overfit alpha-discovery engine. You "
        "propose trading alphas as JSON expressions; an independent verifier backtests "
        "each OUT-OF-SAMPLE across market regimes, after transaction costs, and keeps "
        "only alphas whose WORST-regime deflated Sharpe beats the bar. Reply with ONLY a "
        "JSON array of alpha expressions in the exact DSL described — no prose, no fences.")
    _MODE = {
        "focus": "Refine the best-known alpha with small structural changes.",
        "dream": "Try a structurally different edge (reversion vs momentum vs range).",
        "recover": "Fall back to simple, certainly-valid alphas.",
    }

    def propose(self, problem, memory: Memory, mind: Mind, k: int):
        best = memory.elites[0][1] if memory.elites else BASELINE_ALPHAS[0]
        ctx = memory.context(k=5) or "(no lessons yet)"
        import json
        user = (f"{problem.brief()}\n\nLessons so far:\n{ctx}\n\n"
                f"Best verified alpha so far (improve on it):\n{json.dumps(best)}\n\n"
                f"Mode: {mind.mode} — {self._MODE[mind.mode]}\n"
                f"Propose {k} different alpha expressions as a JSON array.")
        out, self.last, self.note = [], [], ""
        try:
            text = self.core.complete_text(self._SYSTEM, user, max_tokens=2500)
            for p in _extract_alphas(text):
                alpha = normalize_alpha(p)
                out.append(alpha)
                self.last.append(expr_to_str(alpha)[:48])
        except Exception as e:
            self.note = f"core error ({type(e).__name__}); using baseline alphas"
        i = 0
        while len(out) < k and self.fallback:
            out.append(self.fallback[i % len(self.fallback)])
            i += 1
        return out
