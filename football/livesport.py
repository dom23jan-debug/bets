"""Livesport.cz football data: fixtures/results (with half-time score), per-match statistics (xG, shots,
corners, cards, fouls ... for the match and the 1st half), bookmaker odds incl. opening odds, missing players.

Odds: the same GraphQL endpoint as hockey; `geoIpCode` selects the bookmaker set. CZ = the books the user
bets with (Tipsport, Fortuna, Chance, Betano); other geos (SE, KR, GB, ...) give ~60 international books
that form the market consensus ("wisdom of the crowd") against which Czech prices are judged.
Hosts: www.livesport.cz, local-cz.flashscore.ninja (feeds), global.ds.lsapp.eu (odds, lineups).
"""
import concurrent.futures as cf
import gzip
import json
import os
import re
import zoneinfo

from hockey.livesport import FEED, SITE, get, parse_records

TZ = zoneinfo.ZoneInfo("Europe/Prague")   # Czech local time incl. daylight saving (dates of evening games)

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "football")
STATS_FEED = "https://local-cz.flashscore.ninja/2/x/feed/df_st_1_"
ODDS = "https://global.ds.lsapp.eu/odds/pq_graphql?_hash=oce&eventId={}&projectId=2&geoIpCode={}&geoIpSubdivisionCode={}"
PQ = "https://global.ds.lsapp.eu/pq_graphql?_hash={}&eventId={}&projectId=2"


def event_row(f):
    def num(k):
        v = f.get(k)
        return int(v) if v not in (None, "") else None

    hg, ag = num("AG"), num("AH")
    # football list feeds carry the 2nd-half score (BC/BD); the half-time score is full time minus it
    if num("BA") is not None:
        ht = [num("BA"), num("BB")]
    elif num("BC") is not None and hg is not None and f.get("AC") == "3":
        ht = [hg - num("BC"), ag - num("BD")]
    else:
        ht = [None, None]
    return {
        "id": f["AA"], "start": int(f["AD"]), "home": f["AE"], "away": f["AF"],
        "status": f.get("AB"),            # 1 scheduled, 2 live, 3 finished
        "end": f.get("AC"),               # 3 = 90 min; other codes = extra time / penalties / awarded
        "home_goals": hg, "away_goals": ag,
        "ht": ht,                         # half-time score
        "stage": f.get("_tournament"), "round": f.get("ER"),
    }


def league_page(path):
    html = get(f"{SITE}/fotbal/{path}/")
    meta = {"country_id": re.search(r"country_id = (\d+)", html).group(1),
            "template": re.search(r'tournament_id = "([^"]+)"', html).group(1),
            "season_id": re.search(r"seasonId: (\d+)", html).group(1)}
    return [event_row(f) for f in parse_records(html)], meta


def season_results(meta, season_id, max_pages=40):
    events, seen = [], set()
    for page in range(max_pages):
        text = get(f"{FEED}tr_1_{meta['country_id']}_{meta['template']}_{season_id}_{page}_2_cs_1", feed=True)
        new = [event_row(f) for f in parse_records(text) if f["AA"] not in seen]
        if page > 0 and not new:
            break
        seen.update(e["id"] for e in new)
        events += new
    return events


def archive_season_id(path, label):
    """label '2025-2026' (autumn-spring leagues) or '2025' (calendar-year leagues)."""
    country, slug = path.split("/")
    html = get(f"{SITE}/fotbal/{country}/{slug}-{label}/vysledky/")
    return re.search(r"seasonId: (\d+)", html).group(1)


STAT_KEYS = {"Expected goals (xG)": "xg", "Total shots": "sh", "Shots on target": "sot", "Corner kicks": "cor",
             "Yellow cards": "yc", "Red cards": "rc", "Fouls": "fo", "Offsides": "off", "Goalkeeper saves": "sv",
             "Ball possession": "pos", "Big chances": "bc", "xG on target (xGOT)": "xgot"}
ZERO_IF_MISSING = ("yc", "rc")   # card rows are omitted when nobody was booked
SECTIONS = {"Match": "", "1st Half": "1"}


def match_stats(event_id):
    """{'h_xg': 1.48, 'a_xg': 1.83, 'h_cor': 2, ..., 'h1_cor': 0, ...} for the match and the 1st half."""
    text = get(STATS_FEED + event_id, feed=True)
    out, section = {}, None
    for rec in text.split("¬~"):
        f = dict(kv.split("÷", 1) for kv in rec.split("¬") if "÷" in kv)
        if "SE" in f:
            section = f["SE"]
        if section in SECTIONS and f.get("SG") in STAT_KEYS:
            k, p = STAT_KEYS[f["SG"]], SECTIONS[section]
            try:
                out[f"h{p}_{k}"] = float(f.get("SH", "").split("%")[0].split(" ")[0])
                out[f"a{p}_{k}"] = float(f.get("SI", "").split("%")[0].split(" ")[0])
            except ValueError:
                pass
    for p in SECTIONS.values():
        if f"h{p}_sh" in out or f"h{p}_cor" in out:
            for k in ZERO_IF_MISSING:
                out.setdefault(f"h{p}_{k}", 0.0)
                out.setdefault(f"a{p}_{k}", 0.0)
    return out


def _safe_stats(eid):
    try:
        return match_stats(eid)
    except Exception:
        return None


def stats_for(event_ids, workers=8):
    with cf.ThreadPoolExecutor(workers) as ex:
        return {i: s for i, s in zip(event_ids, ex.map(_safe_stats, event_ids)) if s is not None}


# ----------------------------------------------------------------------------- odds
SUBDIVISION = {"CZ": "CZ10", "GB": "GBENG", "DE": "DEBE"}
SKIP_TYPES = ()


def participants(event_id):
    """(home, away) event-participant ids used by the odds feed (light lineup query, page as fallback)."""
    try:
        d = json.loads(get(PQ.format("dmpe2", event_id)))["data"]["findEventById"]
        side = {ep["type"]["side"]: ep["id"] for ep in d["eventParticipants"]}
        return side["HOME"], side["AWAY"]
    except Exception:
        page = get(f"{SITE}/zapas/{event_id}/")
        return re.search(r'"home":\[\{"id":"[^"]+","eventParticipantId":"([^"]+)".*?'
                         r'"away":\[\{"id":"[^"]+","eventParticipantId":"([^"]+)"', page).groups()


def odds_rows(event_id, geo="CZ", parts=None):
    """All active offers as tuples (bet_type, scope, selection, line, bookmaker, odds, opening_odds).

    Lines: ASIAN_HANDICAP and the away selection of EUROPEAN_HANDICAP are from the selection's own
    perspective; EUROPEAN_HANDICAP home/draw lines are from the home team's perspective."""
    hp, ap = parts or participants(event_id)
    d = json.loads(get(ODDS.format(event_id, geo, SUBDIVISION.get(geo, geo + "01"))))["data"]["findOddsByEventId"]
    if not d:
        return []
    books = {b["bookmaker"]["id"]: b["bookmaker"]["name"] for b in d["settings"]["bookmakers"]}
    rows = []
    for o in d["odds"]:
        bt, scope = o["bettingType"], o["bettingScope"]
        for it in o["odds"]:
            if not it["active"]:
                continue
            side = {hp: "H", ap: "A"}.get(it["eventParticipantId"])
            line = float(it["handicap"]["value"]) if it.get("handicap") else None
            if bt == "DOUBLE_CHANCE":
                sel = {"H": "1X", "A": "X2", None: "12"}[side]
            elif bt == "BOTH_TEAMS_TO_SCORE":
                sel = "ANO" if it["bothTeamsToScore"] else "NE"
            elif bt in ("OVER_UNDER", "ODD_OR_EVEN"):
                sel = it["selection"]
            elif bt == "CORRECT_SCORE":
                sel = it["score"]
            elif bt == "HALF_FULL_TIME":
                sel = it["winner"]
            else:
                sel = {"H": "1", "A": "2", None: "X"}[side]
            try:
                odds, opening = float(it["value"]), float(it["opening"] or it["value"])
            except (TypeError, ValueError):
                continue
            if odds <= 1.0:
                continue
            rows.append((bt, scope, sel, line, books.get(o["bookmakerId"], str(o["bookmakerId"])), odds, opening))
    return rows


def multi_geo_rows(event_id, geos=("CZ", "SE", "KR"), parts=None):
    """Union of offers from several geo bookmaker sets (a bookmaker listed in several geos is kept once)."""
    parts = parts or participants(event_id)
    seen_books, out = set(), []
    for geo in geos:
        try:
            rows = odds_rows(event_id, geo, parts)
        except Exception:
            continue
        books = {r[4] for r in rows} - seen_books
        out += [r for r in rows if r[4] in books]
        seen_books |= books
    return out


def missing_players(event_id):
    """Injured / suspended players from Livesport (list per side, may be empty before team news)."""
    d = json.loads(get(PQ.format("dmpe2", event_id)))["data"]["findEventById"]
    out = {}
    for ep in d.get("eventParticipants") or []:
        side = ep["type"]["side"].lower()
        mp = (ep.get("lineup") or {}).get("missingPlayers") or []
        out[side] = [(m.get("player") or {}).get("listName") or (m.get("player") or {}).get("name") for m in mp]
    return out


# ----------------------------------------------------------------------------- cache
def cache_path(key):
    return os.path.join(CACHE, f"{key}.json.gz")


def load_cache(key):
    p = cache_path(key)
    if os.path.exists(p):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    return {"matches": {}, "stats": {}}


def save_cache(key, cache):
    os.makedirs(CACHE, exist_ok=True)
    with gzip.open(cache_path(key), "wt", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, separators=(",", ":"))


def load_league(key, path, seasons, with_stats=True, refresh_current=True):
    """Return (current_events_incl_fixtures, finished_matches_all_seasons) using a gzip JSON cache.
    Past seasons are downloaded once; the current season is refreshed on every call."""
    cache = load_cache(key)
    current, meta = league_page(path)
    finished = [e for e in current if e["status"] == "3"]
    if refresh_current:
        finished += season_results(meta, meta["season_id"])
    for label in seasons:
        if not any(m.get("season") == label for m in cache["matches"].values()):
            try:
                sid = archive_season_id(path, label)
            except Exception:
                continue
            for e in season_results(meta, sid):
                if e["status"] == "3":
                    e["season"] = label
                    cache["matches"][e["id"]] = e
    for e in finished:
        if e["status"] == "3":
            e["season"] = "current"
            cache["matches"][e["id"]] = e
    if with_stats:
        missing = [i for i, m in cache["matches"].items() if i not in cache["stats"]]
        if missing:
            cache["stats"].update(stats_for(missing))
    save_cache(key, cache)
    matches = [dict(m, **cache["stats"].get(i, {})) for i, m in cache["matches"].items()]
    return current, sorted(matches, key=lambda m: m["start"])
