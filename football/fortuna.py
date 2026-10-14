"""Fortuna (ifortuna.cz) offer API: the full Czech market list of a match incl. statistics markets that
Livesport does not compare - corners, yellow cards, shots, shots on target, fouls, offsides (match totals,
team totals, "more X" 3-way), team goal totals per half.

Host: api.ifortuna.cz (reachable from the cloud container, no key). Lines are taken only when they are
x.5 (no refund ambiguity).
"""
import json
import re
import time
import urllib.request

from .names import match_pair, similarity

API = "https://api.ifortuna.cz/offer"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
           "Accept": "application/json", "Origin": "https://www.ifortuna.cz", "Referer": "https://www.ifortuna.cz/"}
BOOK = "Fortuna"
_TOURS = None


def get(path):
    with urllib.request.urlopen(urllib.request.Request(API + path, headers=HEADERS), timeout=30) as r:
        return json.loads(r.read().decode())


def tournaments():
    global _TOURS
    if _TOURS is None:
        t = get("/structure/api/v1_0/sport/ufo:sprt:00/tournaments?categories=true")
        _TOURS = {x["name"]: x["id"] for x in t["tournaments"]}
    return _TOURS


_FIXTURES = {}


def fixtures(tournament_name):
    if tournament_name in _FIXTURES:
        return _FIXTURES[tournament_name]
    tid = tournaments().get(tournament_name)
    if not tid:
        return []
    out = []
    for f in get(f"/structure/api/v1_0/tournament/{tid}/matches").get("fixtures", []):
        parts = {p["type"]: p for p in f.get("participants", [])}
        if "HOME" not in parts or "AWAY" not in parts:
            continue
        out.append({"id": f["id"], "start": f["startDatetime"] // 1000, "home": parts["HOME"]["name"],
                    "away": parts["AWAY"]["name"], "home_id": parts["HOME"]["id"], "away_id": parts["AWAY"]["id"]})
    _FIXTURES[tournament_name] = out
    return out


def find_fixture(tournament_name, start, home, away):
    cands = [f for f in fixtures(tournament_name) if abs(f["start"] - start) <= 20 * 60]
    return match_pair(home, away, cands)


STAT_WORDS = [("rohových kopů", "cor"), ("žlutých karet", "yc"), ("střel na branku", "sot"), ("střel na bránu", "sot"),
              ("střel", "sh"), ("faulů", "fo"), ("ofsajdů", "off"), ("gólů", "goals")]


def _stat(text):
    for w, k in STAT_WORDS:
        if w in text:
            return k
    return None


def _scope(text):
    if "1. poločas" in text or "1.poločas" in text or "v 1. poločasu" in text:
        return "FIRST_HALF"
    if "2. poločas" in text or "2.poločas" in text:
        return "SECOND_HALF"
    return "FULL_TIME"


def _ou(outcome):
    t = (outcome.get("longName") or outcome.get("name") or "").strip()
    m = re.match(r"(Více|Méně) než\s*([0-9]+(?:\.[0-9]+)?)", t)
    if not m:
        return None
    line = float(m.group(2))
    if (line * 2) % 2 != 1:      # only x.5 lines
        return None
    return ("OVER" if m.group(1) == "Více" else "UNDER"), line


def _side(text, fx):
    """'1' / '2' when the text names the home / away team."""
    sh, sa = similarity(text, fx["home"]), similarity(text, fx["away"])
    if max(sh, sa) < 0.55:
        return None
    return "1" if sh >= sa else "2"


def market_rows(fx):
    """Rows (bt, scope, sel, line, 'Fortuna', odds, previous_odds) for statistics and team-total markets."""
    rows = []
    for mk in get(f"/markets/api/v1_0/fixture/{fx['id']}/markets"):
        name = re.sub(r"\s+", " ", re.sub(r"\(Nepočítá se.*", "", mk.get("marketTypeName") or "")).strip()
        low = name.lower()
        if low.startswith(("hráč", "žolík", "další", "zápas +", "výsledek zápasu +")) or "hráč" in low:
            continue
        stat = _stat(low)
        if stat is None:
            continue
        scope = _scope(low)
        team = (mk.get("specifiers") or {}).get("teamId")
        side = {fx["home_id"]: "1", fx["away_id"]: "2"}.get(team) if team else None
        outs = mk.get("outcomes") or []
        if low.startswith("více ") and stat != "goals":                  # more corners / cards / shots ...
            for o in outs:
                txt = (o.get("name") or "").strip()
                if txt in ("1", "2"):
                    sel = txt
                else:
                    sel = "X" if txt.lower().startswith("stejn") else _side(o.get("longName") or txt, fx)
                if sel:
                    rows.append((f"MORE:{stat}", scope, sel, None, BOOK, o["odds"], o.get("previousOdds")))
            continue
        m_each = re.match(r"každý tým zahraje (\d+) a více rohových kopů", low)
        if m_each:
            for o in outs:
                sel = "ANO" if (o.get("name") or "").lower().startswith("ano") else "NE"
                rows.append(("EACH:cor", scope, sel, float(m_each.group(1)), BOOK, o["odds"], o.get("previousOdds")))
            continue
        if not low.startswith(("počet", "1. poločas:", "2. poločas:")) and side is None:
            # team markets without teamId: '<team> počet gólů v zápasu'
            prefix = name.split(" počet ")[0] if " počet " in name else ""
            side = _side(prefix, fx) if prefix else None
            if side is None:
                continue
        if low.startswith(("1. poločas:", "2. poločas:")) and side is None:
            prefix = name.split(":", 1)[1].split(" počet ")[0] if " počet " in name else ""
            side = _side(prefix, fx) if prefix else None
            if side is None:
                continue
        if stat == "goals" and side is None:
            continue                                                   # match goal totals come from Livesport
        if "počet" not in low:
            continue
        for o in outs:
            ou = _ou(o)
            if not ou:
                continue
            sel, line = ou
            if side:
                rows.append((f"TEAM:{stat}", scope, f"{side} {sel}", line, BOOK, o["odds"], o.get("previousOdds")))
            else:
                rows.append((f"TOTAL:{stat}", scope, sel, line, BOOK, o["odds"], o.get("previousOdds")))
    return rows


def rows_for(tournament_name, start, home, away):
    """Fortuna statistics rows for a Livesport fixture, [] when not offered / not matched."""
    if not tournament_name:
        return [], None
    try:
        fx = find_fixture(tournament_name, start, home, away)
        if not fx:
            return [], None
        time.sleep(0.1)
        return market_rows(fx), fx
    except Exception:
        return [], None
