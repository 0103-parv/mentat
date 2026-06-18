"""Realm-mind — toward "omniscient in ONE realm" (honestly), for the stock market.

The honest target (see VISION.md): not predicting the market — that's impossible, the
market is adversarial and non-stationary and the backtest only certifies the PAST. The
reachable, rare thing is a *self-extending, verification-gated MAP of which edges
survive out-of-sample rigor and which are mirages*, that knows its own coverage and
only ever holds what passed the brutal gate.

This studies the market across a broad space of facets, gates every hypothesis through
the deflated-OOS verifier, accumulates a PERSISTENT knowledge map (verified edges +
ruled-out facets), and LOOPS UNTIL DRY (no new verified edge for K rounds) — the
operational definition of "we've mapped what this gate can confirm here." Every claim
is proven; honest negatives are first-class. A verified market edge is provisional: it
survived OOS+cost+deflation on THIS history, not a promise about the future.

  python3 -m mentat.realm                      # synthetic market, loop until dry
  python3 -m mentat.realm --data data/fred_SP500.csv
  python3 -m mentat.realm --report             # print the accumulated realm map
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .curriculum import study
from .trade_lab import load_price_csv, synthetic_universe

MAP_PATH = Path(__file__).parent / "realm_knowledge.json"
DRY_ROUNDS = 2          # stop after this many rounds add NO new verified edge
MAX_ROUNDS = 8          # hard cap so an unattended run always terminates

# A broad space of market facets — each a question + the features a hypothesis may use.
# (v1 is a fixed-but-wide space; auto-GENERATING new facets via the LLM proposer is the
# next layer toward fuller coverage.)
REALM_FACETS = [
    ("short_reversion", "Does the last bar's move reverse?", ["ret1"]),
    ("accel_reversion", "Does momentum acceleration revert?", ["accel", "ret1"]),
    ("short_momentum", "Does 5-bar momentum persist?", ["mom5"]),
    ("medium_momentum", "Does 10-bar momentum persist?", ["mom10"]),
    ("long_momentum", "Does 20-bar momentum persist?", ["mom20"]),
    ("vol_timing", "Does volatility predict returns?", ["vol10", "vol20"]),
    ("vol_scaled_momentum", "Does vol-scaled momentum work?", ["mom20", "vol20"]),
    ("volume_signal", "Does volume carry a signal?", ["volume_z"]),
    ("volume_x_return", "Does volume interact with returns?", ["volume_z", "ret1"]),
    ("trend_distance", "Does distance from trend predict?", ["price_ma_gap"]),
    ("trend_x_momentum", "Does trend interact with momentum?", ["price_ma_gap", "mom20"]),
    ("range_signal", "Does intrabar range predict?", ["hl_range", "vol20"]),
]


def _load_map(market: str) -> dict:
    if MAP_PATH.exists():
        try:
            m = json.loads(MAP_PATH.read_text())
            if m.get("market") == market:
                return m
        except Exception:
            pass
    return {"market": market, "rounds": 0, "facets": {}}


def _merge_round(realm: dict, kb_facets: dict, round_idx: int) -> int:
    """Fold one round's findings into the persistent map. Returns # NEWLY verified."""
    new = 0
    for facet, d in kb_facets.items():
        cur = realm["facets"].get(facet, {"verified": False, "best_score": -1e9,
                                          "tested": 0, "best_alpha": "(none)"})
        if d["verified"] and not cur["verified"]:
            new += 1
        cur["tested"] = cur["tested"] + d["tested"]
        if d["best_deflated_oos_sharpe"] > cur["best_score"]:
            cur["best_score"] = d["best_deflated_oos_sharpe"]
            cur["best_alpha"] = d["best_alpha"]
        cur["verified"] = cur["verified"] or d["verified"]
        cur["last_round"] = round_idx
        realm["facets"][facet] = cur
    return new


def report(realm: dict) -> str:
    facets = realm["facets"]
    verified = [f for f, d in facets.items() if d["verified"]]
    frontier = [f for f, d in facets.items() if not d["verified"]]
    tested = sum(d["tested"] for d in facets.values())
    lines = [
        f"REALM MAP — {realm['market']}  ({realm['rounds']} rounds, {tested} hypotheses gated)",
        "",
        f"  VERIFIED edges ({len(verified)}/{len(facets)} facets) — survived OOS + cost + deflation:",
    ]
    if verified:
        for f in sorted(verified, key=lambda x: -facets[x]["best_score"]):
            d = facets[f]
            lines.append(f"      {f:20} deflated OOS {d['best_score']:+.2f}   {d['best_alpha']}")
    else:
        lines.append("      (none — no hypothesis survived the gate on this market)")
    lines.append("")
    lines.append(f"  RULED OUT / open frontier ({len(frontier)} facets) — searched, no edge held:")
    lines.append("      " + (", ".join(sorted(frontier)) or "(none — every facet has an edge)"))
    lines.append("")
    cov = 100.0 * len(facets) / max(len(REALM_FACETS), 1)
    lines.append(f"  Coverage: {len(facets)}/{len(REALM_FACETS)} facets explored ({cov:.0f}%).")
    lines.append("  Honest caveat: a market edge is PROVISIONAL — it survived our brutal test on "
                 "PAST data;\n  markets are adversarial and non-stationary, so 'verified' means "
                 "'survived', not 'will hold'.")
    return "\n".join(lines)


def map_realm(market: str, bars, *, dry_rounds: int = DRY_ROUNDS,
              max_rounds: int = MAX_ROUNDS, log=print) -> dict:
    realm = _load_map(market)
    dry = 0
    while realm["rounds"] < max_rounds and dry < dry_rounds:
        seed = 100 + realm["rounds"]
        kb, _ = study(market, bars, facets=REALM_FACETS, gens=10, k=16, seed=seed)
        new = _merge_round(realm, kb.facets, realm["rounds"])
        realm["rounds"] += 1
        MAP_PATH.write_text(json.dumps(realm, indent=2))     # checkpoint each round
        dry = dry + 1 if new == 0 else 0
        log(f"  round {realm['rounds']}: {new} new verified edge(s); "
            f"{'dry ' + str(dry) if new == 0 else 'progress'}")
    log(f"  stopped: {'dry (saturated this gate)' if dry >= dry_rounds else 'hit round cap'}")
    return realm


def main() -> int:
    argv = sys.argv[1:]
    if "--report" in argv:
        if not MAP_PATH.exists():
            print("no realm map yet — run `python3 -m mentat.realm` first.")
            return 1
        print(report(json.loads(MAP_PATH.read_text())))
        return 0
    data = None
    if "--data" in argv:
        i = argv.index("--data")
        if i + 1 < len(argv):
            data = argv[i + 1]
    if data:
        bars, market = load_price_csv(data), f"market:{Path(data).stem}"
    else:
        bars, market = synthetic_universe(), "synthetic market"

    print(f"REALM-MIND — mapping {market} until dry (toward omniscient-in-one-realm, honestly)")
    print(f"FACETS   {len(REALM_FACETS)};  GATE   walk-forward OOS + cost + deflated Sharpe\n")
    realm = map_realm(market, bars)
    print("\n" + report(realm))
    print(f"\n(map saved to {MAP_PATH.name}; re-run to deepen coverage — it builds on itself.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
