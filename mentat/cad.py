"""CAD-as-code — design a real parametric part, VERIFIED analytically, with zero GPU.

The driftworks-Jarvis transcript admits real-time 3D needs hardware the user doesn't have. This
routes around that wall: a prototype is defined as PARAMETRIC CODE, and the verifier checks it
ANALYTICALLY — does it fit the envelope, hold the mounting holes with clearance, stay under the
mass budget, and meet a minimum wall thickness for strength. No rendering, no VRAM. The creative
loop searches the design space; only a fully-constraint-satisfying design is believed; the winner
is emitted as printable OpenSCAD you can actually render and 3D-print.

This is "design prototypes WITH me", on the hardware you have — and verified, not vibes.

  python3 -m mentat cad          # design a verified mounting bracket; prints the OpenSCAD
"""
from __future__ import annotations

import math
import random

from .core import BrainConfig, Memory, Problem, Verdict, solve

# --- the design brief: a mounting bracket / plate, constraints in millimetres -------------- #
MAX_W, MAX_H = 120.0, 80.0          # must fit inside this envelope
MIN_T, MAX_T = 3.0, 10.0            # wall thickness range (min is also the strength floor)
HOLE_D = 5.0                        # mounting-hole diameter
EDGE_MARGIN = 8.0                   # min distance from a hole centre to any edge
HOLE_SPACING = 20.0                 # min centre-to-centre hole spacing (a row of holes)
MIN_SPAN = 60.0                     # the plate must bridge at least this width
MIN_AREA = 2500.0                   # min mounting-surface area (mm^2)
DENSITY = 2.7e-3                    # aluminium, g/mm^3
MASS_BUDGET = 120.0                 # grams


def _mass(w, h, t, n):
    solid = w * h * t
    holes = n * math.pi * (HOLE_D / 2) ** 2 * t
    return (solid - holes) * DENSITY


class BracketDesign(Problem):
    name = "cad-bracket"
    statement = "design a mounting bracket that satisfies every geometric + mass constraint"

    def _params(self, c):
        if not isinstance(c, dict):
            return None
        try:
            return (float(c["w"]), float(c["h"]), float(c["t"]), int(c["holes"]))
        except (KeyError, TypeError, ValueError):
            return None

    def verify(self, candidate) -> Verdict:
        p = self._params(candidate)
        if p is None:
            return Verdict(False, -1e9, "malformed design", suspicious=True)
        w, h, t, n = p
        fails = []
        if not (MIN_SPAN <= w <= MAX_W):
            fails.append(f"width {w:.0f} outside [{MIN_SPAN:.0f},{MAX_W:.0f}]")
        if not (0 < h <= MAX_H):
            fails.append(f"height {h:.0f} > {MAX_H:.0f}")
        if not (MIN_T <= t <= MAX_T):
            fails.append(f"thickness {t:.1f} outside [{MIN_T:.0f},{MAX_T:.0f}]")
        if n < 2:
            fails.append("need >=2 mounting holes")
        if w * h < MIN_AREA:
            fails.append(f"area {w * h:.0f} < {MIN_AREA:.0f}")
        # a row of n holes must fit along the width with edge margins + spacing
        if n >= 2 and w < 2 * EDGE_MARGIN + (n - 1) * HOLE_SPACING:
            fails.append("holes don't fit with clearance")
        if h < 2 * EDGE_MARGIN + HOLE_D:
            fails.append("plate too short for hole clearance")
        mass = _mass(w, h, t, n)
        if mass > MASS_BUDGET:
            fails.append(f"mass {mass:.0f}g > {MASS_BUDGET:.0f}g")
        if fails:
            return Verdict(False, -1000 - len(fails), "; ".join(fails))
        # valid: lighter is better (score = -mass); open-ended so the loop keeps optimising mass
        return Verdict(False, -mass,
                       f"VALID bracket {w:.0f}x{h:.0f}x{t:.1f}mm, {n} holes, mass {mass:.1f}g")

    def solved(self, v: Verdict) -> bool:
        return False                                  # optimise mass over the whole budget

    def behavior(self, candidate):
        p = self._params(candidate)
        return None if p is None else p[3]            # niche = #holes (a design frontier)


class BracketProposer:
    def __init__(self, rng: random.Random):
        self.rng = rng

    def _rand(self):
        return {"w": self.rng.uniform(MIN_SPAN, MAX_W), "h": self.rng.uniform(20, MAX_H),
                "t": self.rng.uniform(MIN_T, MAX_T), "holes": self.rng.randint(2, 4)}

    def _mutate(self, c):
        d = dict(c)
        key = self.rng.choice(["w", "h", "t", "holes"])
        if key == "holes":
            d["holes"] = max(2, min(5, int(c.get("holes", 2)) + self.rng.choice([-1, 1])))
        else:
            d[key] = float(c.get(key, MIN_T)) * self.rng.uniform(0.85, 1.15)
        return d

    def propose(self, problem, memory: Memory, mind, k: int):
        ex = mind.explore_rate()
        pool = [c for _, c in memory.elites] or [c for _, c in memory.archive.values()]
        return [self._rand() if not pool or self.rng.random() < ex
                else self._mutate(self.rng.choice(pool)) for _ in range(k)]


def to_openscad(c: dict) -> str:
    w, h, t, n = c["w"], c["h"], c["t"], int(c["holes"])
    xs = [EDGE_MARGIN + i * (w - 2 * EDGE_MARGIN) / (n - 1) for i in range(n)]   # holes spread along width
    holes = "\n".join(f"    translate([{x:.1f},{h/2:.1f},-1]) cylinder(h={t+2:.1f}, d={HOLE_D}, $fn=32);"
                      for x in xs)
    return (f"// mounting bracket — verified by mentat (mass-optimised, all constraints met)\n"
            f"difference() {{\n"
            f"  cube([{w:.1f}, {h:.1f}, {t:.1f}]);\n{holes}\n}}\n")


def design_bracket(*, seed: int = 0, generations: int = 60, k: int = 24):
    mem = Memory()
    solve(BracketDesign(), BracketProposer(random.Random(seed)), mem,
          generations=generations, k=k, log=lambda *_: None, brain=BrainConfig())
    return mem


# --- a SECOND verified part: a cylindrical standoff/spacer (proves CAD-as-code generalises) -- #
SCREW_CLEAR = 3.4       # M3 clearance hole (mm)
MIN_WALL = 1.5          # min wall around the hole
SP_MAX_OD = 20.0
SP_H_MIN, SP_H_MAX = 8.0, 40.0
SP_MASS_BUDGET = 30.0


class SpacerDesign(Problem):
    name = "cad-spacer"
    statement = "design a cylindrical standoff that satisfies every constraint"

    def _params(self, c):
        if not isinstance(c, dict):
            return None
        try:
            return float(c["od"]), float(c["id"]), float(c["h"])
        except (KeyError, TypeError, ValueError):
            return None

    def verify(self, candidate) -> Verdict:
        p = self._params(candidate)
        if p is None:
            return Verdict(False, -1e9, "malformed spacer", suspicious=True)
        od, idia, h = p
        fails = []
        if not (SCREW_CLEAR <= idia <= od - 2 * MIN_WALL):
            fails.append(f"bore {idia:.1f} must be >= {SCREW_CLEAR} and leave >={MIN_WALL}mm wall")
        if od > SP_MAX_OD:
            fails.append(f"OD {od:.1f} > {SP_MAX_OD:.0f}")
        if not (SP_H_MIN <= h <= SP_H_MAX):
            fails.append(f"height {h:.1f} outside [{SP_H_MIN:.0f},{SP_H_MAX:.0f}]")
        mass = math.pi * ((od / 2) ** 2 - (idia / 2) ** 2) * h * DENSITY
        if mass > SP_MASS_BUDGET:
            fails.append(f"mass {mass:.0f}g > {SP_MASS_BUDGET:.0f}g")
        if fails:
            return Verdict(False, -1000 - len(fails), "; ".join(fails))
        return Verdict(False, -mass, f"VALID standoff OD{od:.1f}/bore{idia:.1f}/h{h:.0f}mm, mass {mass:.1f}g")

    def solved(self, v: Verdict) -> bool:
        return False


class SpacerProposer:
    def __init__(self, rng: random.Random):
        self.rng = rng

    def _rand(self):
        return {"od": self.rng.uniform(6, SP_MAX_OD), "id": self.rng.uniform(SCREW_CLEAR, 8),
                "h": self.rng.uniform(SP_H_MIN, SP_H_MAX)}

    def _mutate(self, c):
        d = dict(c)
        key = self.rng.choice(["od", "id", "h"])
        d[key] = float(c.get(key, SCREW_CLEAR)) * self.rng.uniform(0.85, 1.15)
        return d

    def propose(self, problem, memory: Memory, mind, k: int):
        ex = mind.explore_rate()
        pool = [c for _, c in memory.elites]
        return [self._rand() if not pool or self.rng.random() < ex
                else self._mutate(self.rng.choice(pool)) for _ in range(k)]


def to_openscad_spacer(c: dict) -> str:
    od, idia, h = c["od"], c["id"], c["h"]
    return (f"// cylindrical standoff — verified by mentat (mass-optimised, all constraints met)\n"
            f"difference() {{\n"
            f"  cylinder(h={h:.1f}, d={od:.1f}, $fn=48);\n"
            f"  translate([0,0,-1]) cylinder(h={h+2:.1f}, d={idia:.1f}, $fn=48);\n}}\n")


def design_spacer(*, seed: int = 0, generations: int = 60, k: int = 24):
    mem = Memory()
    solve(SpacerDesign(), SpacerProposer(random.Random(seed)), mem,
          generations=generations, k=k, log=lambda *_: None, brain=BrainConfig())
    return mem


PARTS = {
    "bracket": (BracketDesign, design_bracket, to_openscad),
    "spacer": (SpacerDesign, design_spacer, to_openscad_spacer),
}


def design(part: str = "bracket", *, seed: int = 0, generations: int = 60, k: int = 24):
    """Design any registered part; returns (problem, best_candidate_or_None, openscad_or_None)."""
    Prob, designer, emit = PARTS.get(part, PARTS["bracket"])
    mem = designer(seed=seed, generations=generations, k=k)
    prob, best = Prob(), mem.best_candidate
    if best is None or prob.verify(best).score < -999:
        return prob, None, None
    return prob, best, emit(best)


def main() -> int:
    import sys
    part = next((a for a in sys.argv[1:] if a in PARTS), "bracket")
    print(f"CAD-AS-CODE — design a VERIFIED {part} (analytic checks, zero GPU)\n")
    prob, best, scad = design(part)
    if best is None:
        print("  no fully-valid design found in budget (honest).")
        return 0
    print(f"  best verified design: {prob.verify(best).detail}")
    print("  every constraint provably met — verified analytically, not rendered.\n")
    print(f"  printable OpenSCAD (save as {part}.scad, render in OpenSCAD / slice & print):\n")
    print(scad)
    print("=> A real prototype, designed and VERIFIED on the hardware you have — no GPU, no vibes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
