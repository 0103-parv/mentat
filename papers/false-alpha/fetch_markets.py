"""Fetch REAL independent markets (Task 4) — FX, commodity, crypto.

S&P/DJIA/NASDAQ are ~0.9 correlated, so they are not independent evidence. These three
have different microstructure. Real OHLCV from the Yahoo chart API, written as standard
OHLCV CSVs (date,open,high,low,close,volume) that mentat.trade_lab.load_price_csv reads.
Exits non-zero WITHOUT writing if the network is down — never fabricates.

  cd ~/mentat && python3 papers/false-alpha/fetch_markets.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

# (yahoo symbol, output filename, label)
MARKETS = [
    ("EURUSD=X", "yh_EURUSD.csv", "FX (EUR/USD)"),
    ("GC=F", "yh_GOLD.csv", "commodity (gold futures)"),
    ("BTC-USD", "yh_BTCUSD.csv", "crypto (BTC/USD)"),
]
RANGE = "10y"
DATA = Path(__file__).resolve().parents[2] / "data"
UA = {"User-Agent": "Mozilla/5.0 (research; false-alpha markets fetch)"}


def fetch(sym: str):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?range={RANGE}&interval=1d")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read())
    res = d["chart"]["result"][0]
    ts, q = res["timestamp"], res["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(ts):
        o, h, lo, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, lo, c) or c <= 0:
            continue
        day = dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d")
        rows.append((day, o, h, lo, c, v or 0))
    return rows


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    ok = 0
    for sym, fname, label in MARKETS:
        try:
            rows = fetch(sym)
        except Exception as e:
            print(f"  ! {sym}: {type(e).__name__}: {e}")
            continue
        if len(rows) < 200:
            print(f"  ! {sym}: only {len(rows)} bars — skipping")
            continue
        lines = ["date,open,high,low,close,volume"]
        lines += [f"{d},{o:.6f},{h:.6f},{lo:.6f},{c:.6f},{int(v)}" for d, o, h, lo, c, v in rows]
        (DATA / fname).write_text("\n".join(lines) + "\n")
        print(f"  {label}: {len(rows)} bars -> data/{fname} ({rows[0][0]}..{rows[-1][0]})")
        ok += 1
    if ok == 0:
        print("FAILED: no markets fetched (network down?). Nothing written.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
