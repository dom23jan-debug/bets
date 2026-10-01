"""Livesport.cz data access: fixtures/results (with period scores), per-match statistics and
Czech bookmaker odds (Tipsport, Fortuna, Chance, Betano...).

Hosts: www.livesport.cz, local-cz.flashscore.ninja (feeds), global.ds.lsapp.eu (odds).
"""
import concurrent.futures as cf
import datetime
import json
import os
import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"
SITE = "https://www.livesport.cz"
FEED = "https://local-cz.flashscore.ninja/1/x/feed/"
TZ = datetime.timezone(datetime.timedelta(hours=2))
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def get(url, feed=False, sign=None):
    headers = {"User-Agent": UA, "Referer": SITE + "/"}
    if feed:
        headers["x-fsign"] = sign or feed_sign()
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return r.read().decode("utf-8")


_SIGN = None


def feed_sign():
    global _SIGN
    if not _SIGN:
        _SIGN = re.search(r'feed_sign":"([^"]+)"', get(SITE + "/hokej/svedsko/shl/")).group(1)
    return _SIGN


def parse_records(text):
    """Split a Livesport feed / embedded page payload into event dicts."""
    out, seen, tournament = [], set(), None
    for rec in text.split("¬~"):
        f = dict(kv.split("÷", 1) for kv in rec.split("¬") if "÷" in kv)
        if "ZA" in f:
            tournament = f["ZA"]
        if "AA" in f and "AE" in f and f["AA"] not in seen:
            seen.add(f["AA"])
            f["_tournament"] = tournament
            out.append(f)
    return out


def event_row(f):
    """Normalise a raw Livesport event into a flat dict."""
    def num(k):
        v = f.get(k)
        return int(v) if v not in (None, "") else None

    periods = [(num(h), num(a)) for h, a in (("BA", "BB"), ("BC", "BD"), ("BE", "BF"))]
    return {
        "id": f["AA"],
        "start": int(f["AD"]),
        "home": f["AE"],
        "away": f["AF"],
        "status": f.get("AB"),            # 1 scheduled, 2 live, 3 finished
        "end": f.get("AC"),               # 3 regulation, 10 overtime, 11 shootout
        "home_goals": num("AG"),
        "away_goals": num("AH"),
        "periods": periods,
        "stage": f.get("_tournament"),
    }


def league_page(path):
    """Current-season page: returns (events, meta) where meta has country_id, template, season_id."""
    html = get(f"{SITE}/hokej/{path}/")
    meta = {
        "country_id": re.search(r"country_id = (\d+)", html).group(1),
        "template": re.search(r'tournament_id = "([^"]+)"', html).group(1),
        "season_id": re.search(r"seasonId: (\d+)", html).group(1),
    }
    return [event_row(f) for f in parse_records(html)], meta


def season_results(meta, season_id, max_pages=30):
    """All finished matches of a season (regular season and playoffs), paginated feed."""
    events, seen = [], set()
    for page in range(0, max_pages):
        text = get(f"{FEED}tr_4_{meta['country_id']}_{meta['template']}_{season_id}_{page}_2_cs_1", feed=True)
        new = [event_row(f) for f in parse_records(text) if f["AA"] not in seen]
        if page > 0 and not new:
            break
        for e in new:
            seen.add(e["id"])
        events += new
    return events


def archive_season_id(path, season_label):
    """season_label like '2025-2026' -> numeric season id of that archive season."""
    country, slug = path.split("/")
    html = get(f"{SITE}/hokej/{country}/{slug}-{season_label}/vysledky/")
    return re.search(r"seasonId: (\d+)", html).group(1)


STAT_KEYS = {
    "Shots on Goal": "sog", "Shots off target": "miss", "Blocked shots": "blocked",
    "Penalties": "pen", "Penalty Minutes": "pim", "Power Play Goals": "ppg",
    "Short-handed goals": "shg", "Goalkeeper Saves": "saves", "Faceoffs Won": "fo",
    "Hits": "hits", "Takeaways": "takeaways", "Giveaways": "giveaways",
}


def match_stats(event_id):
    """Full-match team statistics (English labels feed)."""
    text = get(f"https://local-cz.flashscore.ninja/2/x/feed/df_st_1_{event_id}", feed=True)
    out, section = {}, None
    for rec in text.split("¬~"):
        f = dict(kv.split("÷", 1) for kv in rec.split("¬") if "÷" in kv)
        if "SE" in f:
            section = f["SE"]
        if section == "Match" and "SG" in f and f["SG"] in STAT_KEYS:
            k = STAT_KEYS[f["SG"]]
            try:
                out["h_" + k] = float(f.get("SH", "").split("%")[0].split(" ")[0])
                out["a_" + k] = float(f.get("SI", "").split("%")[0].split(" ")[0])
            except ValueError:
                pass
    return out


def stats_for(event_ids, workers=8):
    with cf.ThreadPoolExecutor(workers) as ex:
        return dict(zip(event_ids, ex.map(_safe_stats, event_ids)))


def _safe_stats(eid):
    try:
        return match_stats(eid)
    except Exception:
        return {}


def odds_rows(event_id):
    """All active odds offers: (betting_type, scope, selection, line, bookmaker, odds)."""
    page = get(f"{SITE}/zapas/{event_id}/")
    hp, ap = re.search(r'"home":\[\{"id":"[^"]+","eventParticipantId":"([^"]+)".*?'
                       r'"away":\[\{"id":"[^"]+","eventParticipantId":"([^"]+)"', page).groups()
    d = json.loads(get("https://global.ds.lsapp.eu/odds/pq_graphql?_hash=oce"
                       f"&eventId={event_id}&projectId=2&geoIpCode=CZ&geoIpSubdivisionCode=CZ10"))
    d = d["data"]["findOddsByEventId"]
    books = {b["bookmaker"]["id"]: b["bookmaker"]["name"] for b in d["settings"]["bookmakers"]}
    rows = []
    for o in d["odds"]:
        bt = o["bettingType"]
        if bt == "CORRECT_SCORE":
            continue
        for it in o["odds"]:
            if not it["active"]:
                continue
            side = {hp: "H", ap: "A"}.get(it["eventParticipantId"])
            line = float(it["handicap"]["value"]) if it["handicap"] else None
            if bt == "DOUBLE_CHANCE":
                sel = {"H": "1X", "A": "X2", None: "12"}[side]
            elif bt == "BOTH_TEAMS_TO_SCORE":
                sel = "ANO" if it["bothTeamsToScore"] else "NE"
            elif bt in ("OVER_UNDER", "ODD_OR_EVEN"):
                sel = it["selection"]
            else:
                sel = {"H": "1", "A": "2", None: "X"}[side]
            rows.append((bt, o["bettingScope"], sel, line, books.get(o["bookmakerId"], o["bookmakerId"]),
                         float(it["value"])))
    return rows


def load_league(key, path, seasons=("2025-2026",), with_stats=True, refresh_current=True):
    """Return (current_events_incl_fixtures, finished_matches_all_seasons) using a JSON cache."""
    os.makedirs(CACHE, exist_ok=True)
    cache_file = os.path.join(CACHE, f"{key}.json")
    cache = json.load(open(cache_file)) if os.path.exists(cache_file) else {"matches": {}, "stats": {}}
    current, meta = league_page(path)
    finished = [e for e in current if e["status"] == "3"]
    if refresh_current:
        finished += season_results(meta, meta["season_id"])
    for label in seasons:
        if not any(m.get("season") == label for m in cache["matches"].values()):
            for e in season_results(meta, archive_season_id(path, label)):
                e["season"] = label
                cache["matches"][e["id"]] = e
    for e in finished:
        if e["status"] == "3":
            e["season"] = "current"
            cache["matches"][e["id"]] = e
    if with_stats:
        missing = [i for i, m in cache["matches"].items() if m["status"] == "3" and i not in cache["stats"]]
        cache["stats"].update(stats_for(missing))
    json.dump(cache, open(cache_file, "w"), ensure_ascii=False)
    matches = [dict(m, **cache["stats"].get(i, {})) for i, m in cache["matches"].items() if m["status"] == "3"]
    return current, sorted(matches, key=lambda m: m["start"])
