"""Fetch a REAL cross-sectional equity panel (Task 2b) — no synthetic data.

Downloads daily OHLCV for a basket of liquid large-caps from the Yahoo Finance chart API,
aligns them on common trading days, and writes a wide CSV
(date,<TICK>_close,<TICK>_high,<TICK>_low,<TICK>_volume,...) to data/panel_sp.csv.

This is the ONLY place real market data enters the panel study; panel_lab.load_panel_csv
reads exactly this file, so every real-panel number traces to data downloaded here. If the
network is unavailable the script exits non-zero WITHOUT writing — it never fabricates.

  cd ~/mentat && python3 papers/false-alpha/fetch_panel.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "JPM", "XOM",
           "JNJ", "WMT", "KO", "PG", "HD", "BAC", "CVX"]
RANGE = "10y"
OUT = Path(__file__).resolve().parents[2] / "data" / "panel_sp.csv"
UA = {"User-Agent": "Mozilla/5.0 (research; false-alpha panel fetch)"}


def fetch(ticker: str) -> dict[int, tuple] | None:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?range={RANGE}&interval=1d")
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
        res = d["chart"]["result"][0]
        ts = res["timestamp"]
        q = res["indicators"]["quote"][0]
        out = {}
        for i, t in enumerate(ts):
            c, h, lo, v = q["close"][i], q["high"][i], q["low"][i], q["volume"][i]
            if None in (c, h, lo, v) or c <= 0:
                continue
            out[t] = (c, h, lo, float(v))
        return out
    except Exception as e:
        print(f"  ! {ticker}: {type(e).__name__}: {e}")
        return None


def main() -> int:
    print(f"Fetching {len(TICKERS)} tickers (range={RANGE}) from Yahoo Finance...")
    series = {}
    for tk in TICKERS:
        s = fetch(tk)
        if s:
            series[tk] = s
            print(f"  {tk}: {len(s)} bars")
    if len(series) < 6:
        print(f"FAILED: only {len(series)} tickers fetched — refusing to write a thin/"
              "fabricated panel. (Network down? Re-run when online.)")
        return 1
    # align on common timestamps
    common = set.intersection(*[set(s) for s in series.values()])
    days = sorted(common)
    tickers = sorted(series)
    if len(days) < 200:
        print(f"FAILED: only {len(days)} common trading days across tickers.")
        return 1
    header = ["date"] + [f"{tk}_{f}" for tk in tickers
                         for f in ("close", "high", "low", "volume")]
    lines = [",".join(header)]
    import datetime as _dt
    for t in days:
        row = [_dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")]
        for tk in tickers:
            c, h, lo, v = series[tk][t]
            row += [f"{c:.4f}", f"{h:.4f}", f"{lo:.4f}", f"{v:.0f}"]
        lines.append(",".join(row))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {OUT} : {len(tickers)} assets x {len(days)} aligned days "
          f"({days[0] and _dt.datetime.utcfromtimestamp(days[0]).strftime('%Y-%m-%d')} "
          f"to {_dt.datetime.utcfromtimestamp(days[-1]).strftime('%Y-%m-%d')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
