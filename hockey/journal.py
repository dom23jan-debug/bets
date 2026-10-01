"""Bet journal summary: python3 -m hockey.journal  (reads journal/bets.csv)

Columns: date, league, match, market, selection, bookmaker, odds, stake_pct, ev, closing_odds,
result (win/loss/push/half-win/half-loss/open), profit_pct. CLV = odds / closing_odds - 1.
"""
import collections
import csv
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "journal", "bets.csv")


def main():
    rows = list(csv.DictReader(open(PATH, encoding="utf-8")))
    settled = [r for r in rows if r["result"] not in ("", "open")]
    by = collections.defaultdict(lambda: [0, 0.0, 0.0])
    for r in settled:
        for k in ("ALL", r["league"]):
            by[k][0] += 1
            by[k][1] += float(r["stake_pct"])
            by[k][2] += float(r["profit_pct"] or 0)
    print(f"{'liga':6} {'sázek':>5} {'vsazeno %':>9} {'zisk %':>7} {'ROI':>7}")
    for k, (n, s, p) in sorted(by.items()):
        print(f"{k:6} {n:>5} {s:>9.2f} {p:>7.2f} {100*p/s:>6.1f}%")
    clv = [float(r["odds"]) / float(r["closing_odds"]) - 1 for r in rows if r["closing_odds"]]
    if clv:
        print(f"CLV průměr {100*sum(clv)/len(clv):+.1f} % ({len(clv)} sázek, kladné u "
              f"{sum(c > 0 for c in clv)})")
    print(f"otevřené sázky: {sum(r['result'] in ('', 'open') for r in rows)}")


if __name__ == "__main__":
    main()
