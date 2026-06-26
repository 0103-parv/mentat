"""Dependency-free figures — render the paper's plots as SVG from the JSON artifacts.

matplotlib is blocked here (PEP 668), and the engine is pure-Python by design, so we emit
SVG directly. Produces papers/false-alpha/figs/*.svg: the power surface heatmap, the
survivors/bestOOS-vs-N curves, and the worst-of-k vs single-Sharpe deflation envelope.

  python3.14 papers/false-alpha/plot_svg.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIGS = HERE / "figs"


def _load(name):
    p = HERE / name
    return json.loads(p.read_text()) if p.exists() else None


def _svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" font-family="sans-serif">\n{body}\n</svg>\n')


def _heat(v, vmax):
    """survivors -> color: 0 = pale, high = deep teal/orange."""
    if vmax <= 0:
        return "#f5f5f5"
    t = min(v / vmax, 1.0) ** 0.5
    r = int(245 - 200 * t); g = int(245 - 90 * t); b = int(245 - 180 * t)
    return f"rgb({r},{g},{b})"


def power_surface_svg():
    d = _load("power_surface.json")
    if not d:
        return
    grid = d["grid"]; Ns = d["config"]["Ns"]
    strengths = [r["strength"] for r in grid]
    cw, ch, x0, y0 = 70, 34, 90, 40
    W = x0 + cw * len(Ns) + 30
    H = y0 + ch * len(strengths) + 60
    vmax = max((c["survivors"] for r in grid for c in r["cells"]), default=1)
    cells = []
    for ri, r in enumerate(grid):
        cmap = {c["N"]: c["survivors"] for c in r["cells"]}
        for ci, N in enumerate(Ns):
            v = cmap.get(N, 0)
            x, y = x0 + ci * cw, y0 + ri * ch
            cells.append(f'<rect x="{x}" y="{y}" width="{cw-2}" height="{ch-2}" '
                         f'fill="{_heat(v, vmax)}" stroke="#fff"/>')
            cells.append(f'<text x="{x+cw/2-1}" y="{y+ch/2+4}" font-size="11" '
                         f'text-anchor="middle" fill="#222">{v}</text>')
        cells.append(f'<text x="{x0-8}" y="{y0+ri*ch+ch/2+4}" font-size="11" '
                     f'text-anchor="end">{r["strength"]:.2f}</text>')
    for ci, N in enumerate(Ns):
        cells.append(f'<text x="{x0+ci*cw+cw/2-1}" y="{y0-8}" font-size="11" '
                     f'text-anchor="middle">{N}</text>')
    cells.append(f'<text x="{x0+cw*len(Ns)/2}" y="{H-26}" font-size="12" '
                 f'text-anchor="middle">N (search scale) — detectable-edge threshold rises →</text>')
    cells.append(f'<text x="22" y="{y0+ch*len(strengths)/2}" font-size="12" '
                 f'text-anchor="middle" transform="rotate(-90 22 {y0+ch*len(strengths)/2})">'
                 f'planted edge strength</text>')
    cells.append(f'<text x="{x0}" y="24" font-size="13" font-weight="bold">'
                 f'Gate survivors over (edge × N): same edge, provable at small N, '
                 f'unprovable as N grows</text>')
    (FIGS / "power_surface.svg").write_text(_svg(W, H, "\n".join(cells)))
    print("wrote figs/power_surface.svg")


def _line_chart(name, series, ylabel, title, ymin=None, ymax=None, logx=True):
    W, H, mx, my = 640, 360, 70, 50
    xs_all = sorted({x for _, pts in series for x, _ in pts})
    ys_all = [y for _, pts in series for _, y in pts]
    ymin = min(ys_all + [0]) if ymin is None else ymin
    ymax = max(ys_all) if ymax is None else ymax
    if ymax <= ymin:
        ymax = ymin + 1
    def X(x):
        lo, hi = math.log(min(xs_all)), math.log(max(xs_all))
        return mx + (math.log(x) - lo) / (hi - lo + 1e-9) * (W - mx - 30) if logx else x
    def Y(y):
        return H - my - (y - ymin) / (ymax - ymin) * (H - my - 40)
    colors = ["#1b7a6e", "#c0612a", "#3a55a0", "#8a3a8a"]
    b = [f'<text x="{mx}" y="24" font-size="13" font-weight="bold">{title}</text>']
    b.append(f'<line x1="{mx}" y1="{Y(ymin)}" x2="{W-30}" y2="{Y(ymin)}" stroke="#ccc"/>')
    if ymin < 0 < ymax:
        b.append(f'<line x1="{mx}" y1="{Y(0)}" x2="{W-30}" y2="{Y(0)}" stroke="#bbb" '
                 f'stroke-dasharray="3 3"/>')
    for x in xs_all:
        b.append(f'<text x="{X(x)}" y="{H-my+18}" font-size="10" text-anchor="middle">{x}</text>')
    for yy in (ymin, (ymin+ymax)/2, ymax):
        b.append(f'<text x="{mx-8}" y="{Y(yy)+4}" font-size="10" text-anchor="end">{yy:.1f}</text>')
    for i, (label, pts) in enumerate(series):
        c = colors[i % len(colors)]
        path = " ".join(f"{'M' if j==0 else 'L'} {X(x):.1f} {Y(y):.1f}"
                        for j, (x, y) in enumerate(sorted(pts)))
        b.append(f'<path d="{path}" fill="none" stroke="{c}" stroke-width="2"/>')
        for x, y in pts:
            b.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="3" fill="{c}"/>')
        b.append(f'<text x="{W-200}" y="{44+i*16}" font-size="11" fill="{c}">● {label}</text>')
    b.append(f'<text x="{(W)/2}" y="{H-12}" font-size="11" text-anchor="middle">N (log)</text>')
    b.append(f'<text x="18" y="{H/2}" font-size="11" text-anchor="middle" '
             f'transform="rotate(-90 18 {H/2})">{ylabel}</text>')
    (FIGS / name).write_text(_svg(W, H, "\n".join(b)))
    print(f"wrote figs/{name}")


def curves_svg():
    d = _load("nsweep_results.json")
    if not d:
        return
    rows = d["rows"]
    def pts(mkt, gen, key):
        return [(r["N"], r[key]) for r in rows if r["market"] == mkt and r["generator"] == gen]
    _line_chart("survivors_vs_N.svg",
                [("planted (creative)", pts("planted", "creative", "survivors")),
                 ("real S&P (creative)", pts("real:fred_SP500", "creative", "survivors")),
                 ("noise (creative)", pts("noise", "creative", "survivors"))],
                "gate survivors", "Gate survivors vs N — planted rises, real & noise flat at 0")
    _line_chart("bestOOS_vs_N.svg",
                [("real S&P", pts("real:fred_SP500", "creative", "best_naive")),
                 ("noise", pts("noise", "creative", "best_naive")),
                 ("planted", pts("planted", "creative", "best_naive"))],
                "best naive OOS Sharpe", "Naive best-of-N Sharpe vs N — snooping rises on every market")


def envelope_svg():
    d = _load("theory_validation.json")
    if not d:
        return
    wk = d["worst_of_k"]
    _line_chart("deflation_envelope.svg",
                [("single-Sharpe (standard DSR)", [(r["N"], r["k1"]) for r in wk]),
                 ("worst-of-3 regimes (correct)", [(r["N"], r["k3_mc"]) for r in wk])],
                "expected best-of-N (std-normal units)",
                "Deflation envelope: DSR is ~2.4× too large for the worst-of-regimes statistic",
                ymin=0)


def main() -> int:
    FIGS.mkdir(exist_ok=True)
    power_surface_svg(); curves_svg(); envelope_svg()
    print(f"figures -> {FIGS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
