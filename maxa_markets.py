"""Maxa liga multi-market value scanner (1X2, totals, handicaps, BTTS, DNB, double chance,
1st period, odd/even, winner incl. OT). Prices every market from the model's score matrix,
blends EV 50/50 with the bookmakers' no-vig consensus and lists bets with EV >= 1.03.

Usage: python3 maxa_markets.py 2026-09-30
"""
import collections
import datetime
import json
import math
import re
import sys

from maxa_value import (DRAW_TARGET, K, L_A, L_H, PRIOR, TZ, events, get, regulation)

P1_SHARE = 0.322      # share of 60-min goals in the 1st period (league data)
OT_HOME = 0.55        # home share of OT/shootout wins
TOTALS_BOOST = 1.04   # in-sample calibration: raw Poisson overstates unders by ~3 pp
W = 0.5               # weight of the model vs market consensus
EV_MIN = 1.03
NAMES = {"HOME_DRAW_AWAY": "1X2", "DOUBLE_CHANCE": "Dvojitá šance", "DRAW_NO_BET": "Sázka bez remízy",
         "BOTH_TEAMS_TO_SCORE": "Obě dají gól", "OVER_UNDER": "Počet gólů", "ASIAN_HANDICAP": "Handicap",
         "ODD_OR_EVEN": "Lichý/sudý", "HOME_AWAY": "Vítěz vč. prodl."}
SCOPES = {"FULL_TIME": "60 min", "FIRST_PERIOD": "1. třetina", "FULL_TIME_OVER_TIME": "vč. prodl."}


def pmf(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)


def score_matrix(lh, la, draw_adjust=True):
    m = [[pmf(i, lh) * pmf(j, la) for j in range(16)] for i in range(16)]
    if draw_adjust:
        px = sum(m[i][i] for i in range(16))
        want = DRAW_TARGET * 0.5 + px * 0.5 * 1.35
        m = [[v * (want / px if i == j else (1 - want) / (1 - px)) for j, v in enumerate(row)]
             for i, row in enumerate(m)]
    return m


def line_prob(m, value_fn, line):
    """(win, push) for a bet that wins when value_fn(i, j) > line; handles quarter lines."""
    if (line * 4) % 2 == 1:
        return ("split", line_prob(m, value_fn, line - 0.25), line_prob(m, value_fn, line + 0.25))
    win = push = 0.0
    for i in range(16):
        for j in range(16):
            v = value_fn(i, j)
            if v > line:
                win += m[i][j]
            elif v == line:
                push += m[i][j]
    return (win, push)


def expected_return(prob, odds):
    if prob[0] == "split":
        return 0.5 * expected_return(prob[1], odds) + 0.5 * expected_return(prob[2], odds)
    win, push = prob
    return win * odds + push


def model_prob(bt, scope, sel, line, m_ft, m_p1, p_ft):
    if scope == "FULL_TIME_OVER_TIME":
        if bt != "HOME_AWAY":
            return None
        ot = OT_HOME if sel == "1" else 1 - OT_HOME
        return (p_ft[sel] + p_ft["X"] * ot, 0)
    m = m_p1 if scope == "FIRST_PERIOD" else m_ft
    rng = range(16)
    p1 = sum(m[i][j] for i in rng for j in rng if i > j)
    px = sum(m[i][i] for i in rng)
    p2 = 1 - p1 - px
    if bt == "HOME_DRAW_AWAY":
        return ({"1": p1, "X": px, "2": p2}[sel], 0)
    if bt == "DOUBLE_CHANCE":
        return ({"1X": p1 + px, "X2": px + p2, "12": p1 + p2}[sel], 0)
    if bt == "DRAW_NO_BET":
        return (p1 if sel == "1" else p2, px)
    if bt == "BOTH_TEAMS_TO_SCORE":
        both = sum(m[i][j] for i in range(1, 16) for j in range(1, 16))
        return (both if sel == "ANO" else 1 - both, 0)
    if bt == "OVER_UNDER":
        over = sel == "OVER"
        return line_prob(m, (lambda i, j: i + j) if over else (lambda i, j: -(i + j)), line if over else -line)
    if bt == "ASIAN_HANDICAP":
        home = sel == "1"
        return line_prob(m, (lambda i, j: i - j) if home else (lambda i, j: j - i), -line)
    if bt == "ODD_OR_EVEN":
        odd = sum(m[i][j] for i in rng for j in rng if (i + j) % 2)
        return (odd if sel == "ODD" else 1 - odd, 0)
    return None


def odds_rows(event_id):
    page = get(f"https://www.livesport.cz/zapas/{event_id}/")
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
            rows.append((bt, o["bettingScope"], sel, line, books[o["bookmakerId"]], float(it["value"])))
    return rows


def market_fair_odds(rows):
    """No-vig fair odds per selection, averaged across bookmakers."""
    groups = collections.defaultdict(list)
    for r in rows:
        bt, scope, sel, line = r[:4]
        key_line = (line if sel == "1" else -line) if bt == "ASIAN_HANDICAP" else line
        groups[(r[4], bt, scope, key_line)].append(r)
    fair = collections.defaultdict(list)
    for (_, bt, _, _), g in groups.items():
        need = 3 if bt in ("HOME_DRAW_AWAY", "DOUBLE_CHANCE") else 2
        if len({(r[2], r[3]) for r in g}) != need:
            continue
        book_sum = sum(1 / r[5] for r in g) / (2 if bt == "DOUBLE_CHANCE" else 1)
        for r in g:
            fair[r[:4]].append(r[5] * book_sum)
    return {k: sum(v) / len(v) for k, v in fair.items()}


def label(key, home, away):
    bt, scope, sel, line = key
    text = {"1": home, "2": away}.get(sel, sel)
    if bt == "ASIAN_HANDICAP":
        text = f"{text} {line:+g}"
    elif bt == "OVER_UNDER":
        text = f"{'Více' if sel == 'OVER' else 'Méně'} než {line:g}"
    elif bt == "ODD_OR_EVEN":
        text = {"ODD": "Lichý", "EVEN": "Sudý"}[sel]
    return f"{NAMES.get(bt, bt)} ({SCOPES[scope]}): {text}"


def main():
    date = datetime.date.fromisoformat(sys.argv[1])
    evs = events()
    stats = collections.defaultdict(lambda: dict(n=0, gf=0, ga=0))
    for f in (f for f in evs if f.get("AB") == "3"):
        h, a = regulation(f)
        for team, gf, ga in ((f["AE"], h, a), (f["AF"], a, h)):
            stats[team]["n"] += 1
            stats[team]["gf"] += gf
            stats[team]["ga"] += ga
    avg = (L_H + L_A) / 2

    def rating(team):
        s, p = stats[team], PRIOR.get(team, 0)
        return ((s["gf"] + (avg + p / 2) * K) / (s["n"] + K) / avg,
                (s["ga"] + (avg - p / 2) * K) / (s["n"] + K) / avg)

    today = [f for f in evs if datetime.datetime.fromtimestamp(int(f["AD"]), TZ).date() == date]
    for f in sorted(today, key=lambda f: int(f["AD"])):
        home, away = f["AE"], f["AF"]
        (ah, dh), (aa, da) = rating(home), rating(away)
        lh, la = L_H * ah * da * TOTALS_BOOST, L_A * aa * dh * TOTALS_BOOST
        m_ft = score_matrix(lh, la)
        m_p1 = score_matrix(lh * P1_SHARE, la * P1_SHARE, draw_adjust=False)
        rng = range(16)
        p_ft = {"1": sum(m_ft[i][j] for i in rng for j in rng if i > j),
                "X": sum(m_ft[i][i] for i in rng)}
        p_ft["2"] = 1 - p_ft["1"] - p_ft["X"]

        rows = odds_rows(f["AA"])
        fair = market_fair_odds(rows)
        best = {}
        for r in rows:
            if r[:4] in fair and (r[:4] not in best or r[5] > best[r[:4]][1]):
                best[r[:4]] = (r[4], r[5])
        found = []
        for key, (book, odds) in best.items():
            prob = model_prob(*key, m_ft, m_p1, p_ft)
            if prob is None:
                continue
            ev = W * expected_return(prob, odds) + (1 - W) * odds / fair[key]
            if ev >= EV_MIN:
                found.append((ev, key, book, odds))
        start = datetime.datetime.fromtimestamp(int(f["AD"]), TZ)
        print(f"\n{start:%H:%M} {home} - {away}  (očekávané góly 60 min {lh + la:.2f})")
        for ev, key, book, odds in sorted(found, reverse=True) or []:
            print(f"  EV {ev:.3f} | {label(key, home, away):48} @ {odds:.2f} {book}")
        if not found:
            print("  bez value")


if __name__ == "__main__":
    main()
