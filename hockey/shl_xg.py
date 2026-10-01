"""SHL expected goals from official play-by-play (shl.se Sportality API, shot coordinates).

* fetch: schedule per season + play-by-play per game → compact shot list (data/shl_shots.json)
* model: logistic regression P(goal | distance, angle, rebound, period) fitted on past seasons
* attach: per-game xG (60 min, empty-net excluded) to the Livesport match cache (h_xg / a_xg)

Usage: python3 -m hockey.shl_xg
"""
import concurrent.futures as cf
import datetime
import json
import math
import os
import urllib.request

import numpy as np
from scipy.optimize import minimize

from .livesport import CACHE, UA

API = "https://www.shl.se/api"
SEASONS = {"2024-2025": "qeb-73bZkIm9A", "2025-2026": "xs4m9qupsi", "current": "ndcf81nlb3"}
SERIES, REGULAR = "qQ9-bb0bzEWUk", "qQ9-af37Ti40B"
SHOTS_FILE = os.path.join(CACHE, "shl_shots.json")


def get(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def schedule(season_uuid):
    d = get(f"/sports-v2/game-schedule?seasonUuid={season_uuid}&seriesUuid={SERIES}"
            f"&gameTypeUuid={REGULAR}&gamePlace=all&played=all")
    return d["gameInfo"]


def secs(t):
    m, s = t.split(":")
    return int(m) * 60 + int(s)


def compact_pbp(uuid):
    try:
        events = get(f"/gameday/play-by-play/{uuid}")
    except Exception:
        return None
    shots = []
    for e in events:
        if e.get("type") not in ("shot", "goal") or e.get("locationX") is None:
            continue
        place = (e.get("eventTeam") or {}).get("place")
        if place not in ("home", "away"):
            continue
        shots.append([e["period"], secs(e["time"]), place, e["locationX"], e["locationY"],
                      1 if e["type"] == "goal" else 0, 1 if e.get("isEmptyNetGoal") else 0,
                      e.get("goalStatus") or ""])
    return shots


def fetch():
    cache = json.load(open(SHOTS_FILE)) if os.path.exists(SHOTS_FILE) else {}
    for label, su in SEASONS.items():
        games = [g for g in schedule(su) if g["state"] == "post-game"]
        todo = [g for g in games if g["uuid"] not in cache]
        with cf.ThreadPoolExecutor(8) as ex:
            for g, shots in zip(todo, ex.map(compact_pbp, [g["uuid"] for g in todo])):
                if shots is None:
                    continue
                cache[g["uuid"]] = {"season": label, "start": g["rawStartDateTime"],
                                    "home": g["homeTeamInfo"]["names"]["long"],
                                    "away": g["awayTeamInfo"]["names"]["long"],
                                    "hs": g["homeTeamInfo"].get("score"), "as": g["awayTeamInfo"].get("score"),
                                    "shots": shots}
    json.dump(cache, open(SHOTS_FILE, "w"))
    return cache


def features(x, y, rebound, period):
    d = math.hypot(x, y) / 10.0                   # metres
    ang = math.degrees(math.atan2(abs(y), max(x, 1)))
    return [1.0, d, math.log(d + 1), ang / 90.0, rebound, 1.0 if period == 3 else 0.0]


def shot_rows(game):
    """Feature rows for 60-min, non-empty-net shots; rebound = same team shot within 3 s before."""
    rows = []
    last = {}
    shots = [s for s in game["shots"] if str(s[0]).isdigit() and int(s[0]) <= 3]
    for p, t, place, x, y, goal, en, _ in sorted(shots, key=lambda s: (int(s[0]), s[1])):
        p = int(p)
        if p > 3:
            continue
        reb = 1.0 if place in last and last[place][0] == p and 0 <= t - last[place][1] <= 3 else 0.0
        last[place] = (p, t)
        if en:
            continue
        rows.append((place, features(x, y, reb, p), goal))
    return rows


def fit(cache, seasons=("2024-2025", "2025-2026")):
    X, Y = [], []
    for g in cache.values():
        if g["season"] in seasons:
            for _, f, goal in shot_rows(g):
                X.append(f)
                Y.append(goal)
    X, Y = np.array(X), np.array(Y, float)

    def nll(b):
        z = X @ b
        p = 1 / (1 + np.exp(-z))
        ll = (Y * np.log(p + 1e-12) + (1 - Y) * np.log(1 - p + 1e-12)).sum() - 0.5 * (b[1:] ** 2).sum()
        grad = X.T @ (Y - p) - np.concatenate([[0], b[1:]])
        return -ll, -grad

    b = minimize(nll, np.zeros(X.shape[1]), jac=True, method="L-BFGS-B").x
    p = 1 / (1 + np.exp(-(X @ b)))
    auc = _auc(p, Y)
    return b, {"shots": len(Y), "goals": int(Y.sum()), "xg_sum": float(p.sum()), "auc": auc}


def _auc(p, y):
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    pos = y == 1
    return float((ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum()))


def game_xg(game, b):
    xg = {"home": 0.0, "away": 0.0}
    for place, f, _ in shot_rows(game):
        xg[place] += 1 / (1 + math.exp(-float(np.dot(b, f))))
    return xg["home"], xg["away"]


def attach(cache, b, league_file=os.path.join(CACHE, "shl.json")):
    """Match SHL games to Livesport matches by kick-off time + final score and store h_xg/a_xg."""
    lc = json.load(open(league_file))
    by_key = {}
    for g in cache.values():
        t = int(datetime.datetime.fromisoformat(g["start"].replace("Z", "+00:00")).timestamp())
        by_key[(t // 3600, g["hs"], g["as"])] = g
    hit = 0
    for mid, m in lc["matches"].items():
        g = by_key.get((m["start"] // 3600, m["home_goals"], m["away_goals"]))
        if g:
            hx, ax = game_xg(g, b)
            lc["stats"].setdefault(mid, {}).update({"h_xg": round(hx, 3), "a_xg": round(ax, 3)})
            hit += 1
    json.dump(lc, open(league_file, "w"), ensure_ascii=False)
    return hit


if __name__ == "__main__":
    c = fetch()
    coef, info = fit(c)
    print("games", len(c), "| xG model", info, "| coef", np.round(coef, 3).tolist())
    print("attached to Livesport matches:", attach(c, coef))
