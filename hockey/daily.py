"""Run the value scan for every league with games on a date and build one ticket (best bet per match).

Usage: python3 -m hockey.daily [YYYY-MM-DD] [league ...]
  no date    -> today (Central European time)
  no leagues -> all registered leagues (only those with games that day produce output)
NHL runs separately: python3 nhl_value.py <US date> (games are at night CET).
"""
import datetime
import sys

from .leagues import LEAGUES
from .livesport import TZ
from .scan import analyse

# Lower-variance markets are preferred when EV is similar; exotic tails are penalised.
PREFERRED = {"HOME_DRAW_AWAY": 1.0, "ASIAN_HANDICAP": 1.0, "OVER_UNDER": 1.0, "DRAW_NO_BET": 1.0,
             "HOME_AWAY": 1.0, "DOUBLE_CHANCE": 0.98, "BOTH_TEAMS_TO_SCORE": 0.97, "ODD_OR_EVEN": 0.9}
MAX_ODDS = 3.2   # chosen by Dominik 5 Oct 2026: early-season backtest +10 % ROI, 39 % hits
# Backtest vs. closing odds 2025/26 (hockey.market_bt, 8 leagues): model picks made money only while teams
# had played <= 10 games (+15 % ROI, 381 bets); later the market is better and picks lost ~5-8 %.
EARLY_GAMES = 10


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
    args = sys.argv[1:]
    if args and args[0][:4].isdigit():
        date, leagues = args[0], args[1:]
    else:
        date, leagues = datetime.datetime.now(TZ).date().isoformat(), args
    leagues = leagues or list(LEAGUES)
    picks = []
    for lg in leagues:
        try:
            picks += analyse(lg, date)
        except Exception as exc:  # one broken league must not stop the others
            print(f"\n## {lg}: chyba {exc!r}")
    late = [p for p in picks if p.get("n_games", 0) > EARLY_GAMES]
    ticket = best_per_match([p for p in picks if p.get("n_games", 0) <= EARLY_GAMES])
    print(f"\n## Tiket {date} (1 sázka na zápas, kurz ≤ {MAX_ODDS:g}) — před doporučením ověř každý tip (viz CLAUDE.md)")
    for p in ticket:
        print(f"  {p['start']} [{p['league']}] {p['game']:32} {p['label']:46} @ {p['odds']:.2f} {p['book']:12}"
              f" EV {p['ev']:.3f} | value od {p['min_odds']:.2f} | ¼K {100*p['stake']:.1f} %"
              f" | model {100*p['p_model']:.1f} % trh {100*p['p_market']:.1f} %")
    if not ticket:
        print("  žádná value")
    if late:
        games = sorted({p["game"] for p in late})
        print(f"\n  Mimo tiket (týmy už mají > {EARLY_GAMES} zápasů, kdy model v backtestu proti trhu prodělával): "
              + ", ".join(games))


if __name__ == "__main__":
    main()
