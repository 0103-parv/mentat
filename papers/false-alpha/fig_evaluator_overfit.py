"""Figure for the evaluator-overfitting demo: reads the results JSON, writes a clean SVG line chart.
Dependency-free (matplotlib is PEP668-blocked here), matching the paper's plot_svg.py approach.
Prefers the seed-averaged robustness table (24 seeds x 200 reps, smooth and trustworthy); falls
back to the single-seed demo JSON if the robustness run has not been produced.
  python3.14 papers/false-alpha/fig_evaluator_overfit.py
"""
import json, math
from pathlib import Path

here = Path(__file__).resolve().parent
robust = here / "evaluator_overfit_robustness.json"
if robust.exists():
    rows = json.loads(robust.read_text())["seed_averaged_table"]
else:
    rows = json.loads((here / "evaluator_overfit_demo_results.json").read_text())["rows"]
Ns = [r["N"] for r in rows]
opt = [r["optimized_judge"] for r in rows]
ind = [r["independent_judge"] for r in rows]
tru = [r["true_quality"] for r in rows]

W, H, L, Rm, T, Bm = 720, 440, 72, 210, 54, 60
x0, x1, y0, y1 = L, W - Rm, H - Bm, T
lo, hi = 0.0, max(opt) * 1.08
lg = [math.log10(n) for n in Ns]
lmin, lmax = min(lg), max(lg)
px = lambda n: x0 + (math.log10(n) - lmin) / (lmax - lmin) * (x1 - x0)
py = lambda v: y0 + (v - lo) / (hi - lo) * (y1 - y0)
pts = lambda ys: " ".join(f"{px(Ns[i]):.1f},{py(ys[i]):.1f}" for i in range(len(Ns)))

C_OPT, C_IND, C_TRU, INK, MUT = "#d62728", "#2a78d6", "#1baf7a", "#333333", "#888888"
band = pts(opt) + " " + " ".join(f"{px(Ns[i]):.1f},{py(tru[i]):.1f}" for i in range(len(Ns) - 1, -1, -1))

s = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica,Arial,sans-serif">']
s.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
s.append(f'<text x="{W/2:.0f}" y="26" font-size="16" font-weight="bold" fill="#111" text-anchor="middle">Evaluator overfitting in a generate-and-select loop</text>')
for v in range(0, int(hi) + 1, 4):
    s.append(f'<line x1="{x0}" y1="{py(v):.1f}" x2="{x1}" y2="{py(v):.1f}" stroke="#eee" stroke-width="1"/>')
    s.append(f'<text x="{x0-10}" y="{py(v)+4:.1f}" font-size="12" fill="{MUT}" text-anchor="end">{v}</text>')
s.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="{INK}"/><line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="{INK}"/>')
for n in Ns:
    s.append(f'<text x="{px(n):.1f}" y="{y0+20}" font-size="12" fill="{MUT}" text-anchor="middle">{n}</text>')
s.append(f'<text x="{(x0+x1)/2:.0f}" y="{H-16}" font-size="13" fill="{INK}" text-anchor="middle">number of proposals N (log scale)</text>')
s.append(f'<text x="20" y="{(y0+y1)/2:.0f}" font-size="13" fill="{INK}" text-anchor="middle" transform="rotate(-90 20 {(y0+y1)/2:.0f})">score</text>')
s.append(f'<polygon points="{band}" fill="{C_OPT}" opacity="0.09"/>')
s.append(f'<polyline points="{pts(opt)}" fill="none" stroke="{C_OPT}" stroke-width="2.5"/>')
s.append(f'<polyline points="{pts(ind)}" fill="none" stroke="{C_IND}" stroke-width="2.5"/>')
s.append(f'<polyline points="{pts(tru)}" fill="none" stroke="{C_TRU}" stroke-width="2.5" stroke-dasharray="6,4"/>')
for ys, c in ((opt, C_OPT), (ind, C_IND), (tru, C_TRU)):
    for i in range(len(Ns)):
        s.append(f'<circle cx="{px(Ns[i]):.1f}" cy="{py(ys[i]):.1f}" r="3" fill="{c}"/>')
lx = x1 + 16
s.append(f'<text x="{lx}" y="{y1+40}" font-size="12.5" fill="{C_OPT}" font-weight="bold">optimized judge</text>')
s.append(f'<text x="{lx}" y="{y1+56}" font-size="11" fill="{MUT}">what the loop reports</text>')
s.append(f'<text x="{lx}" y="{y1+86}" font-size="12.5" fill="{C_IND}" font-weight="bold">independent judge</text>')
s.append(f'<text x="{lx}" y="{y1+116}" font-size="12.5" fill="{C_TRU}" font-weight="bold">true quality</text>')
s.append(f'<text x="{lx}" y="{y1+150}" font-size="11" fill="{C_OPT}">shaded gap =</text>')
s.append(f'<text x="{lx}" y="{y1+165}" font-size="11" fill="{C_OPT}">inflation</text>')
s.append('</svg>')
(here / "fig_evaluator_overfit.svg").write_text("\n".join(s))
print("wrote fig_evaluator_overfit.svg")
