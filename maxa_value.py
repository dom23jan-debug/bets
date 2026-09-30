"""Maxa liga value-bet model: Poisson on goal ratings (with preseason prior),
blended 50/50 with Tipsport's no-vig line, vs Czech bookmaker odds from Livesport.

Usage: python3 maxa_value.py 2026-09-30
"""
import collections
import datetime
import json
import math
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"
TZ = datetime.timezone(datetime.timedelta(hours=2))

# Preseason prior: goal difference per game, from title/relegation odds and roster quality.
PRIOR = {"Jihlava": .5, "Zlín": .5, "Vsetín": .4, "Kolín": .2, "Litoměřice": .1, "Chomutov": 0,
         "Třebíč": 0, "Přerov": 0, "Slavia Praha": 0, "Pardubice B": -.2, "Tábor": -.2,
         "Havířov": -.2, "Frýdek-Místek": -.3, "Sokolov": -.4}
K = 8                  # prior weight in games
L_H, L_A = 2.93, 2.43  # 60-min goals home/away (observed shrunk toward typical home edge)
DRAW_TARGET = 0.225    # league 60-min tie rate
MARKET_WEIGHT = 0.5    # blend with no-vig market line
EV_MIN = 1.03


def get(url, referer="https://www.livesport.cz/"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def events():
    page = get("https://www.livesport.cz/hokej/cesko/maxa-liga/")
    seen, out = set(), []
    for rec in page.split("¬~"):
        f = dict(kv.split("÷", 1) for kv in rec.split("¬") if "÷" in kv)
        if "AA" in f and "AE" in f and f["AA"] not in seen:
            seen.add(f["AA"])
            out.append(f)
    return out


def regulation(f):
    return (sum(int(f.get(k) or 0) for k in ("BA", "BC", "BE")),
            sum(int(f.get(k) or 0) for k in ("BB", "BD", "BF")))


def odds_1x2(event_id):
    page = get(f"https://www.livesport.cz/zapas/{event_id}/")
    home_pid = re.search(r'"home":\[\{"id":"[^"]+","eventParticipantId":"([^"]+)"', page).group(1)
    data = json.loads(get("https://global.ds.lsapp.eu/odds/pq_graphql?_hash=oce"
                          f"&eventId={event_id}&projectId=2&geoIpCode=CZ&geoIpSubdivisionCode=CZ10"))
    d = data["data"]["findOddsByEventId"]
    names = {b["bookmaker"]["id"]: b["bookmaker"]["name"] for b in d["settings"]["bookmakers"]}
    out = {}
    for o in d["odds"]:
        if o["bettingType"] == "HOME_DRAW_AWAY" and o["bettingScope"] == "FULL_TIME":
            out[names.get(o["bookmakerId"], o["bookmakerId"])] = {
                ("1" if i["eventParticipantId"] == home_pid else "X" if i["eventParticipantId"] is None else "2"):
                float(i["value"]) for i in o["odds"]}
    return out


def main():
    date = datetime.date.fromisoformat(sys.argv[1])
    evs = events()
    done = [f for f in evs if f.get("AB") == "3"]
    stats = collections.defaultdict(lambda: dict(n=0, gf=0, ga=0))
    for f in done:
        h, a = regulation(f)
        for team, gf, ga in ((f["AE"], h, a), (f["AF"], a, h)):
            s = stats[team]
            s["n"] += 1
            s["gf"] += gf
            s["ga"] += ga
    avg = (L_H + L_A) / 2

    def rating(team):
        s, p = stats[team], PRIOR.get(team, 0)
        return ((s["gf"] + (avg + p / 2) * K) / (s["n"] + K) / avg,
                (s["ga"] + (avg - p / 2) * K) / (s["n"] + K) / avg)

    pmf = lambda k, lam: math.exp(-lam) * lam**k / math.factorial(k)
    today = [f for f in evs if datetime.datetime.fromtimestamp(int(f["AD"]), TZ).date() == date]
    for f in sorted(today, key=lambda f: int(f["AD"])):
        home, away = f["AE"], f["AF"]
        (ah, dh), (aa, da) = rating(home), rating(away)
        lh, la = L_H * ah * da, L_A * aa * dh
        p1 = sum(pmf(i, lh) * pmf(j, la) for i in range(15) for j in range(i))
        px = sum(pmf(i, lh) * pmf(i, la) for i in range(15))
        draw = DRAW_TARGET * 0.5 + px * 0.5 * 1.35
        scale = (1 - draw) / (1 - px)
        model = {"1": p1 * scale, "X": draw, "2": (1 - p1 - px) * scale}

        books = odds_1x2(f["AA"])
        ref = books.get("Tipsport.cz") or next(iter(books.values()))
        margin = sum(1 / v for v in ref.values())
        final = {k: (1 - MARKET_WEIGHT) * model[k] + MARKET_WEIGHT * (1 / ref[k]) / margin for k in "1X2"}

        start = datetime.datetime.fromtimestamp(int(f["AD"]), TZ)
        print(f"\n{start:%H:%M} {home} - {away}  (λ {lh:.2f}:{la:.2f}, marže Tipsport {100*(margin-1):.1f} %)")
        for k in "1X2":
            book, odds = max(((b, v[k]) for b, v in books.items()), key=lambda x: x[1])
            q = final[k]
            ev = q * odds
            kelly = max(0.0, (ev - 1) / (odds - 1)) / 4
            flag = "  <-- VALUE" if ev >= EV_MIN else ""
            print(f"  {k}: model {100*model[k]:4.1f} %  finál {100*q:4.1f} %  value od {EV_MIN/q:.2f} | "
                  f"Tipsport {ref[k]:.2f} | nejlepší {odds:.2f} ({book}) EV {ev:.3f} ¼Kelly {100*kelly:.1f} %{flag}")


if __name__ == "__main__":
    main()
