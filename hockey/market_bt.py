"""Backtest against real bookmaker odds (walk-forward, weekly refits) — which markets, odds bands and
filters would have made money in a past season.

Usage: python3 -m hockey.market_bt [league ...] [--season 2025-2026] [--out data/market_bt.csv.gz]
Needs closing odds from `python3 -m hockey.odds_hist`. Writes one row per priced selection
(model and no-vig market probability, best odds, payout) so strategies can be compared offline.
"""
import csv
import gzip
import math
import sys

from .backtest import WEEK
from .leagues import LEAGUES, is_regular, params
from .livesport import load_league
from .markets import expected_return, market_fair_odds, model_prob, win_prob
from .model import Ratings, calibrate_shape, league_profile, regulation, score_dist
from .odds_hist import load as load_odds

COLS = ["league", "event", "start", "home", "away", "bt", "scope", "sel", "line", "book", "odds",
        "fair", "p_model", "p_market", "ev_model", "ev_market", "payout", "n_games"]


def settle(key, m):
    """Payout per unit stake (0 = loss, 1 = push, odds = win) via a degenerate score distribution."""
    h, a = regulation(m)
    ot_home = 1.0 if (m["home_goals"] or 0) > (m["away_goals"] or 0) else 0.0
    return model_prob(key, {(h, a): 1.0}, {(0, 0): 1.0}, ot_home)


def run(key, season="2025-2026"):
    odds = load_odds(key)
    _, matches = load_league(key, LEAGUES[key]["path"], seasons=("2025-2026", "2024-2025"), refresh_current=False)
    matches = [m for m in matches if m.get("season") in ("2024-2025", "2025-2026")]
    regular = [m for m in matches if is_regular(m)]
    test = [m for m in regular if m.get("season") == season and m["id"] in odds]
    if not test:
        return []
    shape, adj = calibrate_shape([m for m in regular if m.get("season") != season] or regular)
    prev = [m for m in regular if m.get("season") != season]
    prof = league_profile(prev or regular)
    ot_home = 0.5 + 0.5 * (prof["ot_home"] - 0.5)
    prm = params(key)
    out, played = [], {}
    for cut in range(test[0]["start"] - 86400, test[-1]["start"] + 1, WEEK):
        ahead = [m for m in test if cut <= m["start"] < cut + WEEK]
        if not ahead:
            continue
        hist = [m for m in matches if m["start"] < cut]
        r = Ratings(hist, now=cut, current=season, **prm)
        for m in ahead:
            ng = min(played.get(m["home"], 0), played.get(m["away"], 0))
            lh, la = r.expected_goals(m["home"], m["away"])
            ft = score_dist(lh * adj, la * adj, shape)
            rows = [tuple(x) for x in odds[m["id"]]]
            fair = market_fair_odds(rows)
            best = {}
            for x in rows:
                if x[:4] in fair and (x[:4] not in best or x[5] > best[x[:4]][1]):
                    best[x[:4]] = (x[4], x[5])
            for k, (book, o) in best.items():
                pm = model_prob(k, ft, {(0, 0): 1.0}, ot_home)
                if pm is None:
                    continue
                pay = expected_return(settle(k, m), o)
                out.append([key, m["id"], m["start"], m["home"], m["away"], *k, book, o, round(fair[k], 4),
                            round(win_prob(pm), 4), round(1 / fair[k], 4), round(expected_return(pm, o), 4),
                            round(o / fair[k], 4), round(pay, 4), ng])
        for m in ahead:
            for t in (m["home"], m["away"]):
                played[t] = played.get(t, 0) + 1
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    season = args[args.index("--season") + 1] if "--season" in args else "2025-2026"
    dest = args[args.index("--out") + 1] if "--out" in args else "data/market_bt.csv.gz"
    keys = [a for a in args if a in LEAGUES] or list(LEAGUES)
    with gzip.open(dest, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for k in keys:
            rows = run(k, season)
            w.writerows(rows)
            print(k, len({r[1] for r in rows}), "games,", len(rows), "selections", file=sys.stderr)
