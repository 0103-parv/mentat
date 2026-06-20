"""Fast + slow memory — the brain's two-speed learning (Complementary Learning Systems).

CLS (McClelland, McNaughton & O'Reilly, 1995): a FAST store (hippocampus) learns single
episodes quickly; a SLOW store (neocortex) consolidates them into durable, generalized
knowledge during sleep. Mentat already has both halves:

  - FAST (hippocampal):  the grounded `Memory` / RAG — verified lessons, learned per episode.
  - SLOW (neocortical):  LoRA fine-tune — lessons baked into the model's weights (mentat.finetune).

This module is the SLEEP that bridges them. It replays the verified lessons, STRENGTHENS the
corroborated ones, ABSTRACTS recurring lessons into higher-level principles, PRUNES the weak
(forgetting), and EXPORTS a consolidation dataset for the slow LoRA step. The firewall holds:
only already-verified, grounded memory is ever consolidated — sleep never invents.

  python3 -m mentat.consolidate          # demo: replay + abstract + export a consolidation set
"""
from __future__ import annotations

import json
from pathlib import Path

from .core import Lesson, Memory, keywords

CONSOLIDATION_DIR = Path(__file__).parent / "finetune" / "data"


def consolidate(memory: Memory, *, min_overlap: int = 2, decay: float = 0.97) -> dict:
    """One sleep pass over the FAST store: cluster lessons that share vocabulary,
    abstract each cluster into a principle, strengthen the corroborated, prune the weak.
    Mutates `memory` in place; returns a small report."""
    lessons = list(memory.lessons)
    used: set[int] = set()
    clusters: list[list[Lesson]] = []
    for i, a in enumerate(lessons):
        if i in used:
            continue
        ka = keywords(a.when)
        group, used_i = [a], {i}
        for j in range(i + 1, len(lessons)):
            if j not in used and len(ka & keywords(lessons[j].when)) >= min_overlap:
                group.append(lessons[j])
                used_i.add(j)
        used |= used_i
        clusters.append(group)

    new_principles = 0
    for g in clusters:
        if len(g) < 2:
            continue
        common = set.intersection(*(keywords(le.when) for le in g))
        text = (f"Across {len(g)} verified lessons about "
                f"{' '.join(sorted(common)) or 'this domain'}: {g[0].do}")
        if not any(p.get("principle") == text for p in memory.principles):
            memory.principles.append({"principle": text, "support": len(g)})
            new_principles += 1
        for le in g:                              # replay strengthens corroborated memory
            le.corroboration += 1
            le.strength = min(5.0, le.strength + 0.5)

    before = len(memory.lessons)
    memory.decay(decay)                           # sleep also forgets the weak
    return {"lessons": len(memory.lessons), "clusters": len(clusters),
            "new_principles": new_principles, "pruned": before - len(memory.lessons),
            "principles_total": len(memory.principles)}


def export_consolidation_dataset(memory: Memory, out: Path | str = CONSOLIDATION_DIR) -> int:
    """Write the consolidated, VERIFIED memory as a chat-format dataset for the slow LoRA
    step — this is what 'sleep' writes toward long-term weights. Returns example count."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for le in memory.lessons:
        a = le.do + (f" Avoid {le.avoid}." if le.avoid else "")
        rows.append({"messages": [{"role": "user", "content": f"When {le.when}, what should you do?"},
                                  {"role": "assistant", "content": a}]})
    for p in memory.principles:
        rows.append({"messages": [{"role": "user", "content": "State a verified principle you've learned."},
                                  {"role": "assistant", "content": p["principle"]}]})
    (out / "consolidation.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    return len(rows)


def sleep_cycle(memory: Memory, out: Path | str = CONSOLIDATION_DIR) -> dict:
    """The full fast->slow bridge: consolidate the fast store, then export the slow set."""
    report = consolidate(memory)
    report["exported"] = export_consolidation_dataset(memory, out)
    return report


def _demo_memory() -> Memory:
    m = Memory()
    for when, do, avoid, ev in [
        ("building a trading alpha tested out of sample",
         "reuse the verified low-turnover reversion alpha", "high-churn curve fits",
         "verified reversion alpha survived out of sample"),
        ("building a trading alpha judged after costs",
         "prefer low-turnover signals", "alphas that bleed out on transaction costs",
         "low turnover trading alpha held up after costs"),
        ("building a large sidon set with distinct sums",
         "reuse the verified greedy construction", "sets with two equal pairwise sums",
         "verified sidon set construction with distinct sums"),
    ]:
        m.learn(Lesson(when=when, do=do, avoid=avoid, evidence=ev))
    return m


def main() -> int:
    m = _demo_memory()
    print(f"FAST store (hippocampal): {len(m.lessons)} verified lessons before sleep\n")
    rep = sleep_cycle(m)
    print(f"  sleep: {rep['clusters']} clusters -> {rep['new_principles']} new principle(s); "
          f"{rep['lessons']} lessons kept, {rep['pruned']} pruned")
    for p in m.principles:
        print(f"    principle (support {p['support']}): {p['principle']}")
    print(f"\n  exported {rep['exported']} consolidation examples to {CONSOLIDATION_DIR}")
    print("  -> slow step: python3 -m mentat.finetune.train  (LoRA bakes these into weights)")
    print("\n=> Fast verified memory + slow weight consolidation = the brain's two speeds. "
          "Sleep only ever\n   replays what was already PROVEN — it strengthens and abstracts, it never invents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
