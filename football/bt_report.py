"""Summarise market backtests (output of football.market_bt) - ROI of the consensus rule by league, EV band,
market, bookmaker, season phase and odds band, and the effect of the model as a filter.

Usage: python3 -m football.bt_report <market_bt.csv.gz ...> [--price close|open] [--max-odds 3.2]
"""
import collections
import csv
import gzip
import sys

BANDS = ((0.98, 1.0), (1.0, 1.01), (1.01, 1.02), (1.02, 1.03), (1.03, 1.05), (1.05, 1.08), (1.08, 9.0))


def rows(paths, price):
    for p in paths:
        with gzip.open(p, "rt") as f:
            for r in csv.DictReader(f):
                o = r[f"odds_{price}"]
                pc = r[f"p_cons_{price}"]
                pay = r[f"payout_{price}"]
                if not o or not pc or not pay or int(r[f"n_cons_{price}"]) < 3:
                    continue
                o, pc, push = float(o), float(pc), float(r["push_model"])
                r["odds"] = o
                r["ev"] = 1 + (o * pc - 1) * (1 - push)
                r["ev_model"] = o * float(r["p_model"]) + push
                r["pay"] = float(pay)
                r["book"] = r[f"book_{price}"]
                yield r


def table(title, groups):
    print(f"\n{title}")
    for k, v in sorted(groups.items(), key=lambda kv: str(kv[0])):
        n = len(v)
        print(f"  {str(k):28} {n:6d} bets  ROI {100 * (sum(v) / n - 1):+6.1f} %")


def main():
    args = sys.argv[1:]
    price = args[args.index("--price") + 1] if "--price" in args else "close"
    max_odds = float(args[args.index("--max-odds") + 1]) if "--max-odds" in args else 3.2
    paths = [a for a in args if a.endswith(".gz")]
    data = [r for r in rows(paths, price) if r["odds"] <= max_odds]
    bands = collections.defaultdict(list)
    for r in data:
        for lo, hi in BANDS:
            if lo <= r["ev"] < hi:
                bands[f"EV {lo:.2f}-{hi:.2f}"].append(r["pay"])
    table(f"EV vs consensus ({price} prices, odds <= {max_odds:g})", bands)
    pick = [r for r in data if 1.015 <= r["ev"] < 1.06]
    for name, key in (("league", lambda r: r["league"]), ("market", lambda r: f"{r['bt']} {r['scope']}"),
                      ("bookmaker", lambda r: r["book"]),
                      ("phase (min games played)", lambda r: min(int(r["n_games"]) // 5 * 5, 20)),
                      ("odds band", lambda r: next(f"{a}-{b}" for a, b in ((1, 1.5), (1.5, 2), (2, 2.5), (2.5, 3.2), (3.2, 99)) if a <= r["odds"] < b)),
                      ("model agrees (EV_model >= 1)", lambda r: r["ev_model"] >= 1.0)):
        g = collections.defaultdict(list)
        for r in pick:
            g[key(r)].append(r["pay"])
        table(f"EV 1.015-1.06 by {name}", g)


if __name__ == "__main__":
    main()
