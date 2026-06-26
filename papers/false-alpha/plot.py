"""Render the paper's figures from the committed JSON artifacts (camera-ready step).

matplotlib only. The JSON artifacts (nsweep_results.json, power_surface.json,
bootstrap_results.json, panel_results.json) are the source of truth; this script just draws
them. If matplotlib is not installed it prints the install hint and exits 0 (the numbers do
not depend on plotting).

  pip install matplotlib && cd ~/mentat && python3 papers/false-alpha/plot.py
Figures are written to papers/false-alpha/figs/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIGS = HERE / "figs"


def _load(name):
    p = HERE / name
    return json.loads(p.read_text()) if p.exists() else None


def main() -> int:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("matplotlib not installed — `pip install matplotlib` to render figures.")
        print("(The JSON artifacts already contain every number; plotting is cosmetic.)")
        return 0
    FIGS.mkdir(exist_ok=True)

    # Figure 1 — power surface: survivors over (edge strength x N) + threshold
    surf = _load("power_surface.json")
    if surf:
        strengths = [r["strength"] for r in surf["grid"]]
        Ns = surf["config"]["Ns"]
        Z = [[next((c["survivors"] for c in r["cells"] if c["N"] == N), 0) for N in Ns]
             for r in surf["grid"]]
        fig, ax = plt.subplots(figsize=(7, 4.5))
        im = ax.imshow(Z, aspect="auto", origin="lower", cmap="viridis")
        ax.set_xticks(range(len(Ns)), [str(n) for n in Ns])
        ax.set_yticks(range(len(strengths)), [f"{s:.2f}" for s in strengths])
        ax.set_xlabel("N (search scale)")
        ax.set_ylabel("planted edge strength")
        ax.set_title("Gate survivors over (edge strength × N) — detectable edge rises with N")
        fig.colorbar(im, ax=ax, label="survivors")
        fig.tight_layout()
        fig.savefig(FIGS / "power_surface.png", dpi=150)
        plt.close(fig)
        print(f"wrote {FIGS / 'power_surface.png'}")

    # Figure 2 — survivors vs N (real S&P = flat 0; planted rises), bestOOS vs N
    sweep = _load("nsweep_results.json")
    if sweep:
        rows = sweep["rows"]
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
        for mkt, gen, style in [("real:fred_SP500", "creative", "-o"),
                                ("planted", "creative", "-s"),
                                ("noise", "creative", "-^")]:
            pts = sorted([(r["N"], r["best_naive"], r["survivors"]) for r in rows
                          if r["market"] == mkt and r["generator"] == gen])
            if pts:
                xs = [p[0] for p in pts]
                a1.plot(xs, [p[1] for p in pts], style, label=mkt)
                a2.plot(xs, [p[2] for p in pts], style, label=mkt)
        for a, t, yl in [(a1, "naive best-of-N Sharpe vs N", "best pooled-OOS Sharpe"),
                         (a2, "gate survivors vs N", "survivors")]:
            a.set_xscale("log"); a.set_xlabel("N"); a.set_ylabel(yl); a.set_title(t)
            a.legend(fontsize=8); a.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(FIGS / "nsweep_curves.png", dpi=150)
        plt.close(fig)
        print(f"wrote {FIGS / 'nsweep_curves.png'}")

    print(f"figures -> {FIGS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
