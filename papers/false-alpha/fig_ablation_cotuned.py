#!/usr/bin/env python3.14
"""Figure for the co-tuned judge ablation: inflation and true quality per condition vs N.
Reads ablation_cotuned_results.json; writes fig_ablation_cotuned.png (+.svg)."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "ablation_cotuned_results.json").read_text())
rows = data["seed_averaged_table"]
NS = [r["N"] for r in rows]

CONDS = [("A", "fixed single judge", "#666666", "--"),
         ("B", "co-tuned single judge", "#c62828", "-"),
         ("C", "co-tuned ensemble", "#ef6c00", "-"),
         ("D", "independent ensemble", "#1565c0", "-")]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

for c, label, color, ls in CONDS:
    infl = [r[f"{c}_inflation"] for r in rows]
    std = [r[f"{c}_inflation_std"] for r in rows]
    ax1.plot(NS, infl, ls, color=color, marker="o", ms=4, label=label)
    ax1.fill_between(NS, [m - s for m, s in zip(infl, std)],
                     [m + s for m, s in zip(infl, std)], color=color, alpha=0.12)
ax1.set_xscale("log")
ax1.set_xlabel("number of proposals N (log scale)")
ax1.set_ylabel("inflation  (reported score − true quality)")
ax1.set_title("Co-tuning is a Goodhart runaway;\nensembling co-tuned judges does not fix it", fontsize=10)
ax1.legend(fontsize=8, frameon=False)
ax1.spines[["top", "right"]].set_visible(False)

for c, label, color, ls in CONDS:
    tq = [r[f"{c}_true"] for r in rows]
    std = [r[f"{c}_true_std"] for r in rows]
    ax2.plot(NS, tq, ls, color=color, marker="o", ms=4, label=label)
    ax2.fill_between(NS, [m - s for m, s in zip(tq, std)],
                     [m + s for m, s in zip(tq, std)], color=color, alpha=0.12)
ax2.set_xscale("log")
ax2.set_xlabel("number of proposals N (log scale)")
ax2.set_ylabel("true quality of selected winner")
ax2.set_title("Independence also selects genuinely\nbetter candidates", fontsize=10)
ax2.legend(fontsize=8, frameon=False)
ax2.spines[["top", "right"]].set_visible(False)

fig.suptitle("Judge provenance ablation (24 seeds, shaded = ±1 sd): independence from the "
             "search trace, not ensembling, is the active ingredient", fontsize=11, y=1.02)
fig.tight_layout()
for ext in ("png", "svg"):
    fig.savefig(HERE / f"fig_ablation_cotuned.{ext}", dpi=200, bbox_inches="tight")
print("wrote fig_ablation_cotuned.png/.svg")
