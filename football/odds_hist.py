"""Download opening and closing odds of finished matches (Czech books + international consensus books) for
backtests against the market.

Usage: python3 -m football.odds_hist <league ...> [--season 2025-2026] [--geos CZ,SE,KR,GB]
Stores data/football/odds/<league>_<season>.json.gz: {event_id: [[bt, scope, sel, line, book, close, open], ...]}
(main markets only; Livesport keeps the last pre-match odds and the opening odds after the game).
"""
import concurrent.futures
import gzip
import json
import os
import sys

from .leagues import LEAGUES, is_regular
from .livesport import CACHE, load_cache, odds_rows, participants

KEEP = {("HOME_DRAW_AWAY", "FULL_TIME"), ("DRAW_NO_BET", "FULL_TIME"), ("DOUBLE_CHANCE", "FULL_TIME"),
        ("ASIAN_HANDICAP", "FULL_TIME"), ("OVER_UNDER", "FULL_TIME"), ("BOTH_TEAMS_TO_SCORE", "FULL_TIME"),
        ("HOME_DRAW_AWAY", "FIRST_HALF"), ("OVER_UNDER", "FIRST_HALF")}
GEOS = ("CZ", "SE", "KR", "GB")


def path(key, season):
    return os.path.join(CACHE, "odds", f"{key}_{season}.json.gz")


def load(key, season):
    p = path(key, season)
    return json.load(gzip.open(p, "rt")) if os.path.exists(p) else {}


def _fetch(eid, geos):
    try:
        parts = participants(eid)
    except Exception:
        return eid, None
    seen, out = set(), []
    for geo in geos:
        try:
            rows = odds_rows(eid, geo, parts)
        except Exception:
            continue
        books = {r[4] for r in rows} - seen
        seen |= books
        out += [list(r) for r in rows if r[4] in books and (r[0], r[1]) in KEEP]
    return eid, out or None


def update(key, season, geos=GEOS, workers=6):
    have = load(key, season)
    cache = load_cache(key)
    todo = [m["id"] for m in cache["matches"].values() if m.get("season") == season and m["status"] == "3"
            and is_regular(m) and m["id"] not in have]
    with concurrent.futures.ThreadPoolExecutor(workers) as ex:
        for i, (eid, rows) in enumerate(ex.map(lambda e: _fetch(e, geos), todo)):
            if rows:
                have[eid] = rows
            if i % 100 == 99:
                _save(key, season, have)
    _save(key, season, have)
    print(key, season, len(todo), "fetched,", len(have), "stored", flush=True)


def _save(key, season, have):
    os.makedirs(os.path.dirname(path(key, season)), exist_ok=True)
    with gzip.open(path(key, season), "wt") as f:
        json.dump(have, f, separators=(",", ":"))


if __name__ == "__main__":
    args = sys.argv[1:]
    season = args[args.index("--season") + 1] if "--season" in args else "2025-2026"
    geos = tuple(args[args.index("--geos") + 1].split(",")) if "--geos" in args else GEOS
    for k in [a for a in args if a in LEAGUES]:
        update(k, season, geos)
