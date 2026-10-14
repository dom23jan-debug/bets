"""Sofascore API (api.sofascore.com, no key): referee with career card record, missing players
(injuries / suspensions), predicted / confirmed lineups and bet365 odds incl. corners and cards lines
(opening and closing, also for finished matches -> backtest of the statistics models)."""
import json
import time
import urllib.error
import urllib.request

from .names import match_pair

API = "https://api.sofascore.com/api/v1"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/128.0 Safari/537.36", "Accept": "application/json",
           "Referer": "https://www.sofascore.com/"}
_SEASON = {}


def get(path, retries=2):
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(API + path, headers=HEADERS), timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404 or attempt == retries:
                raise
            time.sleep(1.5 * (attempt + 1))
    return None


def season_id(ut, index=0):
    if (ut, index) not in _SEASON:
        _SEASON[(ut, index)] = get(f"/unique-tournament/{ut}/seasons")["seasons"][index]["id"]
    return _SEASON[(ut, index)]


def season_events(ut, sid, direction="last", max_pages=40):
    out = []
    for page in range(max_pages):
        try:
            d = get(f"/unique-tournament/{ut}/season/{sid}/events/{direction}/{page}")
        except urllib.error.HTTPError:
            break
        out += [{"id": e["id"], "start": e["startTimestamp"], "home": e["homeTeam"]["name"],
                 "away": e["awayTeam"]["name"], "status": e["status"]["type"],
                 "hg": (e.get("homeScore") or {}).get("current"), "ag": (e.get("awayScore") or {}).get("current")}
                for e in d.get("events", [])]
        if not d.get("hasNextPage"):
            break
    return out


_EVENTS = {}


def find_event(ut, start, home, away):
    """Sofascore event of a Livesport fixture (same kick-off +- 2 h, most similar team names)."""
    if ut not in _EVENTS:
        try:
            _EVENTS[ut] = (season_events(ut, season_id(ut), "next", max_pages=3)
                           + season_events(ut, season_id(ut), "last", max_pages=1))
        except Exception:
            _EVENTS[ut] = []
    evs = _EVENTS[ut]
    cands = [e for e in evs if abs(e["start"] - start) <= 2 * 3600]
    return match_pair(home, away, cands)


def referee(event_id):
    """{'name', 'games', 'yellow', 'red', 'yellow_red'} (career, all competitions) or None if not assigned."""
    ref = get(f"/event/{event_id}")["event"].get("referee")
    if not ref:
        return None
    return {"name": ref["name"], "games": ref.get("games") or 0, "yellow": ref.get("yellowCards") or 0,
            "red": ref.get("redCards") or 0, "yellow_red": ref.get("yellowRedCards") or 0}


def lineups(event_id):
    """{'confirmed': bool, 'home': [missing...], 'away': [...]} with reasons (injury / suspension)."""
    d = get(f"/event/{event_id}/lineups")
    out = {"confirmed": d.get("confirmed", False)}
    for side in ("home", "away"):
        out[side] = [f"{m['player']['name']} ({m.get('description') or m.get('type')})"
                     for m in d.get(side, {}).get("missingPlayers", [])]
    return out


def frac(s):
    a, b = s.split("/")
    return 1 + int(a) / int(b)


def bet365_lines(event_id):
    """bet365 odds of corners / cards / goals O-U lines: {(market, line): {'OVER': (open, close), ...}}."""
    out = {}
    for m in get(f"/event/{event_id}/odds/1/all").get("markets", []):
        name = {"Corners 2-Way": "cor", "Cards in match": "cards", "Match goals": "goals"}.get(m["marketName"])
        if not name or m.get("choiceGroup") is None:
            continue
        line = float(m["choiceGroup"])
        d = {}
        for c in m["choices"]:
            try:
                d[c["name"].upper()] = (frac(c["initialFractionalValue"]), frac(c["fractionalValue"]))
            except (KeyError, ValueError, ZeroDivisionError):
                pass
        if "OVER" in d and "UNDER" in d:
            out[(name, line)] = d
    return out
