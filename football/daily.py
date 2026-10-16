"""Run the football value scan for every league with games on a date and build one ticket (best bet per match).

Usage: python3 -m football.daily [YYYY-MM-DD] [league ... | europe | all | cups] [--no-extra] [--vse]
  no date    -> today (Central European time)
  no leagues -> all European leagues incl. UEFA cups (leagues without games that day print one line)
  --vse      -> old wide ticket: tier A up to odds 3.2 plus B / C (corners, cards); default is the
                high-hit-rate ticket (tier A, odds 1.5-2.0)
"""
import concurrent.futures as cf
import datetime
import sys

from .leagues import CUPS, EUROPE, LEAGUES
from .livesport import TZ
from .scan import analyse

# Lower-variance markets are preferred when EV is similar; exotic / correlated markets are penalised.
PREFERRED = {"HOME_DRAW_AWAY": 1.0, "ASIAN_HANDICAP": 1.0, "OVER_UNDER": 1.0, "DRAW_NO_BET": 1.0,
             "DOUBLE_CHANCE": 0.98, "BOTH_TEAMS_TO_SCORE": 0.97, "EUROPEAN_HANDICAP": 0.95, "ODD_OR_EVEN": 0.9,
             "HALF_FULL_TIME": 0.7, "CORRECT_SCORE": 0.6}
# Default ticket = high hit rate (Dominik 16 Oct 2026: "velká úspěšnost"). Backtest 2025/26, European first
# divisions, opening prices, one bet per match: tier A at odds 1.5-2.0 won 57 % (+8 % refunds, 35 % lost),
# ROI +5.9 % ±2.1 on 1 350 bets, longest losing run 6; odds 1.5-3.2 won 47 %, ROI +7.8 % ±2.5, run 9.
# Below 1.5 hit rates reach 67-84 % but the Czech margin leaves ROI ~0-1.5 % -> not worth it.
# B (halves ...) and C (corners / cards) are thin evidence -> only with --vse.
MAX_ODDS = 2.0
WIDE_MAX_ODDS = 3.2       # --vse (same cap as hockey)
SAFE_TIERS = ("A", "A!")


TIER_WEIGHT = {"A": 1.0, "A!": 0.6, "B": 0.7, "B!": 0.4, "C": 0.5, "C!": 0.3}
OFF_TICKET = ("S", "AP")


def score(p):
    """Ranking within a match: tier first, then edge vs the consensus, lower-variance markets preferred."""
    return TIER_WEIGHT.get(p["tier"], 0) * (p["ev"] - 1 + 0.01) * PREFERRED.get(p["key"][0], 0.95)


def best_per_match(picks, max_odds=MAX_ODDS, tiers=SAFE_TIERS):
    best = {}
    for p in picks:
        if p["odds"] > max_odds or p["tier"] in OFF_TICKET or (tiers and p["tier"] not in tiers):
            continue
        if p["game"] not in best or score(p) > score(best[p["game"]]):
            best[p["game"]] = p
    return sorted(best.values(), key=lambda p: -score(p))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args and args[0][:4].isdigit():
        date, keys = args[0], args[1:]
    else:
        date, keys = datetime.datetime.now(TZ).date().isoformat(), args
    if not keys or keys == ["europe"]:
        keys = EUROPE
    elif keys == ["all"]:
        keys = list(LEAGUES)
    elif keys == ["cups"]:
        keys = list(CUPS)
    def run(k):
        lines = []
        try:
            return k, lines, analyse(k, date, extra="--no-extra" not in sys.argv, out=lines.append)
        except Exception as exc:  # one broken league must not stop the others
            lines.append(f"\n## {k}: chyba {exc!r}")
            return k, lines, []

    picks, idle = [], []
    with cf.ThreadPoolExecutor(3) as ex:          # leagues in parallel, output kept in league order
        for k, lines, p in ex.map(run, keys):
            if len(lines) == 1 and " 0 zápas" in lines[0]:
                idle.append(k)
                continue
            print("\n".join(lines), flush=True)
            picks += p
    if idle:
        print(f"\nBez zápasů {date}: " + ", ".join(idle))
    wide = "--vse" in sys.argv
    max_odds = WIDE_MAX_ODDS if wide else MAX_ODDS
    ticket = best_per_match(picks, max_odds, None if wide else SAFE_TIERS)
    print(f"\n## Tiket {date} (1 sázka na zápas, {'široký' if wide else 'vysoká úspěšnost: tier A'}, kurz ≤ {max_odds:g}) — před doporučením ověř každý tip (skill football-value)")
    for p in ticket:
        print(f"  {p['start']} [{p['league']}] {p['game']:34} {p['label']:58} @ {p['odds']:.2f} {p['book']:11}"
              f" [{p['tier']}] EV trh {p['ev']:.3f} ({p['source']}, {p['n_books']} k.) model {p['ev_model']:.3f}"
              f" | value od {p['min_odds']:.2f} | vklad {100*p['stake']:.1f} %"
              f" | p model {100*p['p_model']:.1f} %" + (f" trh {100*p['p_market']:.1f} %" if p["p_market"] else ""))
    if not ticket:
        print("  žádná value")
    if not wide:
        on = {p["game"] for p in ticket}
        rest = best_per_match([p for p in picks if p["game"] not in on], WIDE_MAX_ODDS, None)
        if rest:
            print("\n## Mimo tiket (kurz > 2.0 nebo B/C — nižší úspěšnost; zapsat do rejected.csv, vsadit jen s --vse)")
            for p in rest:
                print(f"  {p['start']} [{p['league']}] {p['game']:34} {p['label']:58} @ {p['odds']:.2f} {p['book']:11}"
                      f" [{p['tier']}] EV trh {p['ev']:.3f} model {p['ev_model']:.3f}")
    later = sorted([p for p in picks if p["tier"] == "AP"], key=lambda p: -p["ev"])
    if later:
        print("\n## Nižší / netestované soutěže — value jen pokud vydrží do ~2 h před výkopem (pak spusť sken znovu)")
        seen = set()
        for p in later:
            if p["game"] in seen:
                continue
            seen.add(p["game"])
            print(f"  {p['start']} [{p['league']}] {p['game']:34} {p['label']:58} @ {p['odds']:.2f} {p['book']:11}"
                  f" EV trh {p['ev']:.3f} model {p['ev_model']:.3f} | value od {p['min_odds']:.2f}")
    watch = sorted([p for p in picks if p["tier"] == "S"], key=lambda p: -p["ev_model"])
    if watch:
        print("\n## Sledovat — statistiky jen podle modelu (neověřeno backtestem, NE na tiket; zapsat do rejected.csv)")
        for p in watch[:12]:
            print(f"  {p['start']} [{p['league']}] {p['game']:34} {p['label']:58} @ {p['odds']:.2f} {p['book']:9}"
                  f" EV model {p['ev_model']:.3f} | p model {100*p['p_model']:.1f} %")


if __name__ == "__main__":
    main()
