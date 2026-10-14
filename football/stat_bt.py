"""Backtest of the corners / cards models against bet365 lines (opening and closing, from Sofascore).

Usage: python3 -m football.stat_bt <league ...> [--season-index 1]
  season-index 1 = previous season on Sofascore (2025/26 while 2026/27 runs)
Downloads data/football/sofa/<league>_<season>.json.gz once, maps events to Livesport matches, refits the
count models weekly and reports log-loss (model vs bet365 no-vig) and ROI of betting the model's side at
bet365 prices for several EV thresholds.
"""
import concurrent.futures as cf
import gzip
import json
import math
import os
import sys

from . import sofascore
from .backtest import WEEK
from .leagues import LEAGUES, params
from .livesport import CACHE, load_cache
from .model import GoalModel, StatModels, nb_pmf, stat_pair
from .names import match_pair


def path(key, label):
    return os.path.join(CACHE, "sofa", f"{key}_{label}.json.gz")


def download(key, season_index=1):
    ut = LEAGUES[key]["sofa"]
    seasons = sofascore.get(f"/unique-tournament/{ut}/seasons")["seasons"]
    sid, label = seasons[season_index]["id"], seasons[season_index]["year"].replace("/", "-")
    p = path(key, label)
    have = json.load(gzip.open(p, "rt")) if os.path.exists(p) else {}
    evs = [e for e in sofascore.season_events(ut, sid, "last", max_pages=60) if e["status"] == "finished"]
    todo = [e for e in evs if str(e["id"]) not in have]

    def fetch(e):
        try:
            return e, {f"{k[0]}|{k[1]}": v for k, v in sofascore.bet365_lines(e["id"]).items()}
        except Exception:
            return e, None

    with cf.ThreadPoolExecutor(3) as ex:
        for e, lines in ex.map(fetch, todo):
            if lines is not None:
                have[str(e["id"])] = dict(e, lines=lines)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with gzip.open(p, "wt") as f:
        json.dump(have, f, separators=(",", ":"))
    print(key, label, len(todo), "fetched,", len(have), "stored", flush=True)
    return have


def p_over(mu, k, line):
    pm = nb_pmf(int(mu * 4 + 40), mu, k)
    return sum(pm[int(math.floor(line)) + 1:])


def run(key, season_index=1, thresholds=(1.0, 1.03, 1.05, 1.08, 1.12)):
    sofa = download(key, season_index)
    cache = load_cache(key)
    matches = sorted([dict(m, **cache["stats"].get(i, {})) for i, m in cache["matches"].items()
                      if m.get("home_goals") is not None], key=lambda m: m["start"])
    season = LEAGUES[key]["seasons"][season_index - 1]
    test = [m for m in matches if m.get("season") == season]
    by_time = {}
    for e in sofa.values():
        by_time.setdefault(e["start"] // 3600, []).append(e)
    pairs = []
    for m in test:
        cands = by_time.get(m["start"] // 3600, []) + by_time.get(m["start"] // 3600 - 1, []) + \
            by_time.get(m["start"] // 3600 + 1, [])
        e = match_pair(m["home"], m["away"], cands)
        if e:
            pairs.append((m, e))
    prm = params(key)
    res = {st: {"ll_m": 0.0, "ll_b": 0.0, "n": 0, "bets": {t: [0, 0.0] for t in thresholds}}
           for st in ("cor", "cards")}
    if not pairs:
        return res
    for cut in range(pairs[0][0]["start"] - 86400, pairs[-1][0]["start"] + 1, WEEK):
        ahead = [(m, e) for m, e in pairs if cut <= m["start"] < cut + WEEK]
        if not ahead:
            continue
        hist = [m for m in matches if m["start"] < cut]
        gm = GoalModel(hist, cut, current=season, **prm)
        sm = StatModels(hist, gm.weights, ridge=8.0, keys=("cor", "cards"))
        for m, e in ahead:
            for st in ("cor", "cards"):
                if st not in sm.models:
                    continue
                y = stat_pair(m, st)
                lines = [(float(k.split("|")[1]), v) for k, v in e["lines"].items() if k.split("|")[0] == st]
                if not y or not lines:
                    continue
                total = y[0] + y[1]
                mh, ma = sm.models[st].rates(m["home"], m["away"])
                k = sm.k_total[st]
                for line, d in lines:
                    po = p_over(mh + ma, k, line)
                    oo, uo = d["OVER"][1], d["UNDER"][1]
                    pb = (1 / oo) / (1 / oo + 1 / uo)
                    won_over = total > line
                    r = res[st]
                    r["ll_m"] -= math.log(max(1e-9, po if won_over else 1 - po))
                    r["ll_b"] -= math.log(max(1e-9, pb if won_over else 1 - pb))
                    r["n"] += 1
                    # bet the model's side at bet365 opening prices
                    for side, p, odds, win in (("OVER", po, d["OVER"][0], won_over), ("UNDER", 1 - po, d["UNDER"][0], not won_over)):
                        ev = p * odds
                        for t in thresholds:
                            if ev >= t:
                                b = res[st]["bets"][t]
                                b[0] += 1
                                b[1] += (odds - 1) if win else -1
    for st, r in res.items():
        if r["n"]:
            print(f"{key} {st}: n {r['n']} | log-loss model {r['ll_m']/r['n']:.4f} vs bet365 close {r['ll_b']/r['n']:.4f} | "
                  + " ".join(f"EV≥{t:g}: {b[0]} bets ROI {100*b[1]/b[0]:+.1f} %" for t, b in r["bets"].items() if b[0]),
                  flush=True)
    return res


if __name__ == "__main__":
    args = sys.argv[1:]
    si = int(args[args.index("--season-index") + 1]) if "--season-index" in args else 1
    for k in [a for a in args if a in LEAGUES]:
        run(k, si)
