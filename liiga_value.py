"""Liiga value-bet model: Poisson on shrunk xG/goal ratings vs Veikkaus 1X2 odds.

Usage: python3 liiga_value.py 2026-09-30 [season]
"""
import json
import math
import sys
import urllib.request
from collections import defaultdict

XG_WEIGHT = 0.8   # blend of xG vs actual goals in team ratings
SHRINK = 6        # prior weight (in games) pulling ratings to league average
DRAW_BOOST = 1.30 # Poisson underestimates 60-min ties in hockey
EV_MIN = 1.03


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def regulation(game):
    per = [p for p in game["periods"] if p["category"] == "NORMAL"]
    return sum(p["homeTeamGoals"] for p in per), sum(p["awayTeamGoals"] for p in per)


def poisson(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)


def main():
    date = sys.argv[1]
    season = sys.argv[2] if len(sys.argv) > 2 else "2027"
    games = fetch(f"https://liiga.fi/api/v2/games?tournament=runkosarja&season={season}")
    done = [g for g in games if g["ended"] and g["serie"] == "RUNKOSARJA"]

    stats = defaultdict(lambda: dict(n=0, gf=0, ga=0, xf=0.0, xa=0.0))
    for g in done:
        h, a = regulation(g)
        for side, opp, gf, ga in (("homeTeam", "awayTeam", h, a), ("awayTeam", "homeTeam", a, h)):
            s = stats[g[side]["teamName"]]
            s["n"] += 1
            s["gf"] += gf
            s["ga"] += ga
            s["xf"] += g[side]["expectedGoals"] or 0
            s["xa"] += g[opp]["expectedGoals"] or 0

    n = len(done)
    home_avg = sum(regulation(g)[0] for g in done) / n
    away_avg = sum(regulation(g)[1] for g in done) / n
    avg = (home_avg + away_avg) / 2

    def rating(team):
        s = stats[team]
        att = (XG_WEIGHT * s["xf"] + (1 - XG_WEIGHT) * s["gf"]) / s["n"]
        de = (XG_WEIGHT * s["xa"] + (1 - XG_WEIGHT) * s["ga"]) / s["n"]
        shrink = lambda v: (v * s["n"] + avg * SHRINK) / (s["n"] + SHRINK) / avg
        return shrink(att), shrink(de)

    for g in (g for g in games if g["start"].startswith(date)):
        home, away = g["homeTeam"]["teamName"], g["awayTeam"]["teamName"]
        (ah, dh), (aa, da) = rating(home), rating(away)
        lh, la = home_avg * ah * da, away_avg * aa * dh
        p1 = px = p2 = 0.0
        for i in range(15):
            for j in range(15):
                p = poisson(i, lh) * poisson(j, la)
                if i > j:
                    p1 += p
                elif i == j:
                    px += p
                else:
                    p2 += p
        px *= DRAW_BOOST
        k = (1 - px) / (p1 + p2)
        probs = (p1 * k, px, p2 * k)

        print(f"\n{home} - {away}  (xG model λ {lh:.2f}:{la:.2f})")
        ev_odds = g.get("gamblingEvent") or {}
        odds = [ev_odds.get(key, 0) / 100 for key in ("homeTeamOdds", "tieOdds", "awayTeamOdds")]
        for label, p, o in zip("1X2", probs, odds):
            line = f"  {label}: model {p*100:5.1f} %  fair {1/p:5.2f}  value od {EV_MIN/p:5.2f}"
            if o:
                ev = p * o
                kelly = max(0.0, (p * o - 1) / (o - 1))
                line += f" | Veikkaus {o:.2f} ({100/o:.1f} %) EV {ev:.3f} ¼Kelly {kelly/4*100:.1f} %"
            print(line)


if __name__ == "__main__":
    main()
