"""Backtest against real bookmaker odds (walk-forward, weekly refits) - which markets, thresholds and
filters would have made money at the Czech bookmakers in a past season.

Usage: python3 -m football.market_bt <league ...> [--season 2025-2026] [--out <file.csv.gz>]
Needs odds from `python3 -m football.odds_hist`. Writes one row per priced Czech offer (best Czech price per
selection) with model probability, consensus probability at opening and at closing, both prices and the
payout, so strategies can be compared offline (e.g. pandas: ROI by EV threshold / market / odds band / phase).
"""
import csv
import gzip
import sys

from .backtest import WEEK
from .leagues import LEAGUES, is_regular, params
from .livesport import load_cache
from .markets import CZ_BOOKS, consensus, expected_return, model_prob, push_prob, win_prob
from .model import GoalModel, fit_rho, half_dist, half_tie_factor, league_profile, score_dist
from .odds_hist import load as load_odds
from .markets import htft
from .scan import implied_lambdas

COLS = ["league", "event", "start", "home", "away", "n_games", "bt", "scope", "sel", "line", "book_close",
        "odds_close", "book_open", "odds_open", "p_model", "p_cons_close", "n_cons_close", "p_cons_open",
        "n_cons_open", "p_impl_close", "p_impl_open", "push_model", "payout_close", "payout_open"]


def ctx_for(lh, la, rho, prof):
    s1 = prof.get("h1_share", 0.45)
    h1 = half_dist(lh * s1, la * s1, half_tie_factor(prof, lh, la, 1))
    h2 = half_dist(lh * (1 - s1), la * (1 - s1), half_tie_factor(prof, lh, la, 2))
    return {"ft": score_dist(lh, la, rho), "h1": h1, "h2": h2, "htft": htft(h1, h2), "stats": {}}


def real_ctx(m):
    hg, ag = m["home_goals"], m["away_goals"]
    ht = m.get("ht") or [None, None]
    ctx = {"ft": {(hg, ag): 1.0}, "stats": {}}
    if ht[0] is not None:
        ctx["h1"] = {(ht[0], ht[1]): 1.0}
        ctx["h2"] = {(hg - ht[0], ag - ht[1]): 1.0}
    return ctx


def run(key, season="2025-2026"):
    odds = load_odds(key, season)
    cache = load_cache(key)
    matches = sorted([dict(m, **cache["stats"].get(i, {})) for i, m in cache["matches"].items()
                      if m.get("home_goals") is not None], key=lambda m: m["start"])
    test = [m for m in matches if m.get("season") == season and is_regular(m) and m["id"] in odds]
    if not test:
        return []
    prm = params(key)
    out, played = [], {}
    first = test[0]["start"]
    for cut in range(first - 86400, test[-1]["start"] + 1, WEEK):
        ahead = [m for m in test if cut <= m["start"] < cut + WEEK]
        if not ahead:
            continue
        hist = [m for m in matches if m["start"] < cut]
        gm = GoalModel(hist, cut, current=season, **prm)
        regular = [m for m in hist if is_regular(m)][-700:]
        prof = league_profile(regular)
        rho = fit_rho(regular[-400:], gm) if len(regular) > 100 else -0.06
        for m in ahead:
            ng = min(played.get(m["home"], 0), played.get(m["away"], 0))
            lh, la = gm.expected_goals(m["home"], m["away"])
            ctx = ctx_for(lh, la, rho, prof)
            rctx = real_ctx(m)
            rows = [tuple(x) for x in odds[m["id"]]]
            cons_c = consensus(rows, price=5)
            cons_o = consensus(rows, price=6)
            impl = {}
            for tag, cons in (("close", cons_c), ("open", cons_o)):
                mk = implied_lambdas(cons, rho)
                impl[tag] = ctx_for(mk[0], mk[1], rho, prof) if mk else None
            best = {}
            for r in rows:
                if r[4] not in CZ_BOOKS:
                    continue
                k = r[:4]
                b = best.setdefault(k, [None, 0.0, None, 0.0])
                if r[5] > b[1]:
                    b[0], b[1] = r[4], r[5]
                if r[6] and r[6] > b[3]:
                    b[2], b[3] = r[4], r[6]
            for k, (bc, oc, bo, oo) in best.items():
                pm = model_prob(k, ctx)
                if pm is None:
                    continue
                if k[1] != "FULL_TIME" and "h1" not in rctx:
                    continue
                settle = model_prob(k, rctx)
                if settle is None:
                    continue
                pi_c = model_prob(k, impl["close"]) if impl["close"] else None
                pi_o = model_prob(k, impl["open"]) if impl["open"] else None
                cc, co = cons_c.get(k), cons_o.get(k)
                out.append([key, m["id"], m["start"], m["home"], m["away"], ng, *k, bc, oc, bo, oo,
                            round(win_prob(pm), 4), round(cc[0], 4) if cc else "", cc[1] if cc else 0,
                            round(co[0], 4) if co else "", co[1] if co else 0,
                            round(win_prob(pi_c), 4) if pi_c else "", round(win_prob(pi_o), 4) if pi_o else "",
                            round(push_prob(pm), 4), round(expected_return(settle, oc), 4),
                            round(expected_return(settle, oo), 4) if oo else ""])
        for m in ahead:
            for t in (m["home"], m["away"]):
                played[t] = played.get(t, 0) + 1
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    season = args[args.index("--season") + 1] if "--season" in args else "2025-2026"
    dest = args[args.index("--out") + 1] if "--out" in args else "market_bt.csv.gz"
    keys = [a for a in args if a in LEAGUES]
    with gzip.open(dest, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for k in keys:
            rows = run(k, season)
            w.writerows(rows)
            print(k, len({r[1] for r in rows}), "games,", len(rows), "offers", file=sys.stderr, flush=True)
