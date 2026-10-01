"""Run the value scan for several leagues and build one ticket (best bet per match).

Usage: python3 -m hockey.daily 2026-10-01 shl del nl elh sk fr
"""
import sys

from .scan import analyse

# Lower-variance markets are preferred when EV is similar; exotic tails are penalised.
PREFERRED = {"HOME_DRAW_AWAY": 1.0, "ASIAN_HANDICAP": 1.0, "OVER_UNDER": 1.0, "DRAW_NO_BET": 1.0,
             "HOME_AWAY": 1.0, "DOUBLE_CHANCE": 0.98, "BOTH_TEAMS_TO_SCORE": 0.97, "ODD_OR_EVEN": 0.9}
MAX_ODDS = 6.0


def best_per_match(picks):
    best = {}
    for p in picks:
        if p["odds"] > MAX_ODDS:
            continue
        score = (p["ev"] - 1) * PREFERRED.get(p["key"][0], 0.95) * (0.85 if p["key"][1] == "FIRST_PERIOD" else 1)
        if p["game"] not in best or score > best[p["game"]][0]:
            best[p["game"]] = (score, p)
    return [p for _, p in sorted(best.values(), key=lambda x: -x[0])]


def main():
    date, leagues = sys.argv[1], sys.argv[2:]
    picks = []
    for lg in leagues:
        picks += analyse(lg, date)
    ticket = best_per_match(picks)
    print("\n## Tiket (1 sázka na zápas, kurz ≤ 6)")
    for p in ticket:
        print(f"  {p['start']} [{p['league']}] {p['game']:32} {p['label']:46} @ {p['odds']:.2f} {p['book']:12}"
              f" EV {p['ev']:.3f} | value od {p['min_odds']:.2f} | ¼K {100*p['stake']:.1f} %")


if __name__ == "__main__":
    main()
