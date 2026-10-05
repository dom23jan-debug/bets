"""Download pre-match (closing) odds of finished matches for backtests against the market.

Usage: python3 -m hockey.odds_hist <league ...> [--season 2025-2026]
Stores data/odds/<league>.json.gz: {event_id: [[bt, scope, sel, line, book, odds], ...]}
(60-min and incl.-OT markets only; Livesport keeps the last pre-match odds after the game).
"""
import concurrent.futures
import gzip
import json
import os
import sys

from .leagues import LEAGUES, is_regular
from .livesport import CACHE, odds_rows

KEEP = {"HOME_DRAW_AWAY", "HOME_AWAY", "DRAW_NO_BET", "DOUBLE_CHANCE", "ASIAN_HANDICAP", "OVER_UNDER"}


def path(key):
    return os.path.join(CACHE, "odds", f"{key}.json.gz")


def load(key):
    p = path(key)
    return json.load(gzip.open(p, "rt")) if os.path.exists(p) else {}


def _fetch(eid):
    try:
        return eid, [list(r) for r in odds_rows(eid) if r[0] in KEEP and r[1] != "FIRST_PERIOD"]
    except Exception:
        return eid, None


def update(key, season="2025-2026"):
    have = load(key)
    matches = json.load(open(os.path.join(CACHE, f"{key}.json")))["matches"].values()
    todo = [m["id"] for m in matches if m.get("season") == season and m["status"] == "3"
            and is_regular(m) and m["id"] not in have]
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        for eid, rows in ex.map(_fetch, todo):
            if rows:
                have[eid] = rows
    os.makedirs(os.path.dirname(path(key)), exist_ok=True)
    with gzip.open(path(key), "wt") as f:
        json.dump(have, f, separators=(",", ":"))
    print(key, len(todo), "fetched,", len(have), "stored")


if __name__ == "__main__":
    args = sys.argv[1:]
    season = args[args.index("--season") + 1] if "--season" in args else "2025-2026"
    for k in [a for a in args if a in LEAGUES] or list(LEAGUES):
        update(k, season)
