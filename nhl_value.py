"""NHL multi-market value scanner.

Model:
  * team strength = current roster weighted by last season's on-ice xG/60 (MoneyPuck) blended with
    last season's team xG and goals, regressed toward league average for the offseason;
  * goalie = tonight's starter (DailyFaceoff) with shrunk GSAx/60; back-to-back penalty;
  * 60-min score distribution = Poisson + late-game goalie-pull phase (empty-net goals, late equalisers),
    fitted to all 1,312 games of 2025-26 (margins, totals, 24.8 % regulation ties);
  * every market priced from that distribution, EV blended with the bookmakers' no-vig consensus.

Usage: python3 nhl_value.py 2026-09-30   (NHL date, US time)
Needs: api-web.nhle.com, moneypuck.com, www.dailyfaceoff.com, www.livesport.cz, global.ds.lsapp.eu
"""
import collections
import csv
import datetime
import io
import json
import math
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"
MP = "https://moneypuck.com/moneypuck/playerData/seasonSummary/{season}/regular/{kind}.csv"
LAST_SEASON = 2025

# Score model fitted to 2025-26 (see docstring)
BASE_H, BASE_A = 2.95, 2.82          # league base rates fed into the score model (60 min, before EN phase)
LATE, EN_LEAD, EN_SECOND, LATE_EQ, TIE = 0.06, 0.55, 0.25, 0.30, 1.30
P1_SHARE, P1_TIE = 0.30, 1.06        # 1st period
OT_HOME = 0.49                        # home share of OT/SO wins in 2025-26
REGRESS = 0.25                        # offseason regression to league mean
ROSTER_W = 0.5                        # roster-based vs last season's team rating
B2B = 0.07                            # goals/60 penalty (attack and defence) on 2nd night of back-to-back
GOALIE_SHRINK = 35                    # games of prior for GSAx (two-season pooled)
W_MODEL = 0.4                         # NHL lines are sharp: 40 % model, 60 % market
EV_MIN = 1.03
N = 15

NAMES = {"HOME_DRAW_AWAY": "1X2", "DOUBLE_CHANCE": "Dvojitá šance", "DRAW_NO_BET": "Sázka bez remízy",
         "BOTH_TEAMS_TO_SCORE": "Obě dají gól", "OVER_UNDER": "Počet gólů", "ASIAN_HANDICAP": "Handicap",
         "ODD_OR_EVEN": "Lichý/sudý", "HOME_AWAY": "Vítěz vč. prodl."}
SCOPES = {"FULL_TIME": "60 min", "FIRST_PERIOD": "1. třetina", "FULL_TIME_OVER_TIME": "vč. prodl."}
LIVESPORT_NAMES = {"PHI": "Philadelphia", "PIT": "Pittsburgh", "TOR": "Toronto", "NYI": "Islanders",
                   "COL": "Colorado", "LAK": "Los Angeles", "NJD": "New Jersey", "NYR": "Rangers",
                   "TBL": "Tampa", "BUF": "Buffalo", "CBJ": "Columbus", "MIN": "Minnesota",
                   "NSH": "Nashville", "SEA": "Seattle", "CGY": "Calgary", "CHI": "Chicago", "UTA": "Utah",
                   "EDM": "Edmonton", "VAN": "Vancouver", "FLA": "Florida", "SJS": "San Jose",
                   "BOS": "Boston", "MTL": "Montreal", "OTT": "Ottawa", "DET": "Detroit", "CAR": "Carolina",
                   "WSH": "Washington", "STL": "St. Louis", "DAL": "Dallas", "WPG": "Winnipeg",
                   "ANA": "Anaheim", "VGK": "Vegas"}


def get(url, referer=None):
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return r.read().decode("utf-8")


def mp_csv(kind, season=LAST_SEASON):
    return [r for r in csv.DictReader(io.StringIO(get(MP.format(season=season, kind=kind))))
            if r["situation"] == "all"]


def pmf(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)


def score_dist(lh, la):
    """60-min score distribution with late goalie-pull phase."""
    mh, ma = lh * (1 - LATE), la * (1 - LATE)
    base = {(i, j): pmf(i, mh) * pmf(j, ma) for i in range(N) for j in range(N)}
    tie_mass = sum(v for (i, j), v in base.items() if i == j)
    dist = collections.defaultdict(float)
    for (i, j), p in base.items():
        p *= TIE if i == j else (1 - tie_mass * TIE) / (1 - tie_mass)
        diff = i - j
        if abs(diff) in (1, 2):
            none = 1 - EN_LEAD - LATE_EQ
            if diff > 0:
                moves = [((0, 1), LATE_EQ), ((1, 0), EN_LEAD * (1 - EN_SECOND)), ((2, 0), EN_LEAD * EN_SECOND),
                         ((0, 0), none)]
            else:
                moves = [((1, 0), LATE_EQ), ((0, 1), EN_LEAD * (1 - EN_SECOND)), ((0, 2), EN_LEAD * EN_SECOND),
                         ((0, 0), none)]
            for (dx, dy), q in moves:
                dist[(i + dx, j + dy)] += p * q
        else:
            for x in range(4):
                for y in range(4):
                    dist[(i + x, j + y)] += p * pmf(x, lh * LATE) * pmf(y, la * LATE)
    return dist


def period_dist(lh, la):
    base = {(i, j): pmf(i, lh) * pmf(j, la) for i in range(10) for j in range(10)}
    tie_mass = sum(v for (i, j), v in base.items() if i == j)
    return {(i, j): v * (P1_TIE if i == j else (1 - tie_mass * P1_TIE) / (1 - tie_mass))
            for (i, j), v in base.items()}


class Ratings:
    def __init__(self):
        self.skaters = {r["playerId"]: r for r in mp_csv("skaters")}
        # goalies: last two seasons, the older one at 60 % weight (single goalie seasons are noisy)
        self.goalies = collections.defaultdict(lambda: [0.0, 0.0, 0.0])  # weighted gsax, hours, games
        for season, w in ((LAST_SEASON, 1.0), (LAST_SEASON - 1, 0.6)):
            for r in mp_csv("goalies", season):
                g = self.goalies[r["name"].lower()]
                g[0] += w * (float(r["xGoals"]) - float(r["goals"]))
                g[1] += w * float(r["icetime"]) / 3600
                g[2] += w * float(r["games_played"])
        self.teams = {r["team"]: r for r in mp_csv("teams")}
        ice = sum(float(r["iceTime"]) for r in self.teams.values()) / 3600
        self.league = sum(float(r["xGoalsFor"]) for r in self.teams.values()) / ice

    def team(self, abbrev):
        roster = json.loads(get(f"https://api-web.nhle.com/v1/roster/{abbrev}/current"))
        players = []
        for pos, key in (("F", "forwards"), ("D", "defensemen")):
            for p in roster[key]:
                s = self.skaters.get(str(p["id"]))
                if s and float(s["games_played"]) >= 10:
                    ice = float(s["icetime"]) / 3600
                    players.append((pos, float(s["icetime"]) / float(s["games_played"]) / 60,
                                    float(s["OnIce_F_xGoals"]) / ice, float(s["OnIce_A_xGoals"]) / ice))
                else:  # rookie / no NHL sample: replacement level
                    players.append((pos, 12.0 if pos == "F" else 16.0, self.league - 0.15, self.league + 0.15))
        lineup = (sorted((p for p in players if p[0] == "F"), key=lambda p: -p[1])[:12]
                  + sorted((p for p in players if p[0] == "D"), key=lambda p: -p[1])[:6])
        toi = sum(p[1] for p in lineup)
        r_for = sum(p[1] * p[2] for p in lineup) / toi
        r_against = sum(p[1] * p[3] for p in lineup) / toi
        t = self.teams.get(abbrev)
        if t:
            ice = float(t["iceTime"]) / 3600
            h_for = 0.8 * float(t["xGoalsFor"]) / ice + 0.2 * float(t["goalsFor"]) / ice
            h_against = float(t["xGoalsAgainst"]) / ice
            r_for = ROSTER_W * r_for + (1 - ROSTER_W) * h_for
            r_against = ROSTER_W * r_against + (1 - ROSTER_W) * h_against
        regress = lambda v: (1 - REGRESS) * v + REGRESS * self.league
        return regress(r_for), regress(r_against)

    def goalie(self, name):
        gsax, hours, gp = self.goalies.get(name.lower(), (0.0, 0.0, 0.0))
        if not hours:
            return -0.10
        return gsax / hours * gp / (gp + GOALIE_SHRINK)


def starting_goalies(date):
    page = get(f"https://www.dailyfaceoff.com/starting-goalies/{date}")
    data = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S).group(1))
    return {(g["homeTeamName"], g["awayTeamName"]): g for g in data["props"]["pageProps"]["data"]}


def livesport_events():
    page = get("https://www.livesport.cz/hokej/usa/nhl/")
    out = {}
    for rec in page.split("¬~"):
        f = dict(kv.split("÷", 1) for kv in rec.split("¬") if "÷" in kv)
        if "AA" in f and "AE" in f:
            out.setdefault(f["AA"], f)
    return out.values()


def odds_rows(event_id):
    page = get(f"https://www.livesport.cz/zapas/{event_id}/")
    hp, ap = re.search(r'"home":\[\{"id":"[^"]+","eventParticipantId":"([^"]+)".*?'
                       r'"away":\[\{"id":"[^"]+","eventParticipantId":"([^"]+)"', page).groups()
    d = json.loads(get("https://global.ds.lsapp.eu/odds/pq_graphql?_hash=oce"
                       f"&eventId={event_id}&projectId=2&geoIpCode=CZ&geoIpSubdivisionCode=CZ10",
                       referer="https://www.livesport.cz/"))["data"]["findOddsByEventId"]
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


def line_prob(dist, value_fn, line):
    if (line * 4) % 2 == 1:  # quarter line: half on each neighbour
        return ("split", line_prob(dist, value_fn, line - 0.25), line_prob(dist, value_fn, line + 0.25))
    win = sum(p for (i, j), p in dist.items() if value_fn(i, j) > line)
    push = sum(p for (i, j), p in dist.items() if value_fn(i, j) == line)
    return (win, push)


def expected_return(prob, odds):
    if prob[0] == "split":
        return 0.5 * expected_return(prob[1], odds) + 0.5 * expected_return(prob[2], odds)
    return prob[0] * odds + prob[1]


def model_prob(key, ft, p1):
    bt, scope, sel, line = key
    if scope == "FULL_TIME_OVER_TIME":
        if bt != "HOME_AWAY":
            return None
        h = sum(p for (i, j), p in ft.items() if i > j)
        x = sum(p for (i, j), p in ft.items() if i == j)
        return (h + x * OT_HOME, 0) if sel == "1" else (1 - h - x + x * (1 - OT_HOME), 0)
    dist = p1 if scope == "FIRST_PERIOD" else ft
    h = sum(p for (i, j), p in dist.items() if i > j)
    x = sum(p for (i, j), p in dist.items() if i == j)
    a = 1 - h - x
    if bt == "HOME_DRAW_AWAY":
        return ({"1": h, "X": x, "2": a}[sel], 0)
    if bt == "DOUBLE_CHANCE":
        return ({"1X": h + x, "X2": x + a, "12": h + a}[sel], 0)
    if bt == "DRAW_NO_BET":
        return (h if sel == "1" else a, x)
    if bt == "BOTH_TEAMS_TO_SCORE":
        both = sum(p for (i, j), p in dist.items() if i > 0 and j > 0)
        return (both if sel == "ANO" else 1 - both, 0)
    if bt == "OVER_UNDER":
        if sel == "OVER":
            return line_prob(dist, lambda i, j: i + j, line)
        return line_prob(dist, lambda i, j: -(i + j), -line)
    if bt == "ASIAN_HANDICAP":
        if sel == "1":
            return line_prob(dist, lambda i, j: i - j, -line)
        return line_prob(dist, lambda i, j: j - i, -line)
    if bt == "ODD_OR_EVEN":
        odd = sum(p for (i, j), p in dist.items() if (i + j) % 2)
        return (odd if sel == "ODD" else 1 - odd, 0)
    return None


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
    date = sys.argv[1]
    schedule = json.loads(get(f"https://api-web.nhle.com/v1/schedule/{date}"))["gameWeek"][0]["games"]
    yesterday = (datetime.date.fromisoformat(date) - datetime.timedelta(days=1)).isoformat()
    played_yesterday = {t["abbrev"] for g in json.loads(get(f"https://api-web.nhle.com/v1/score/{yesterday}"))["games"]
                        for t in (g["homeTeam"], g["awayTeam"])}
    goalies = starting_goalies(date)
    ratings = Ratings()
    events = list(livesport_events())
    for g in schedule:
        if g["gameType"] != 2:
            continue
        h, a = g["homeTeam"]["abbrev"], g["awayTeam"]["abbrev"]
        (hf, ha), (af, aa) = ratings.team(h), ratings.team(a)
        for team, sign in ((h, 1), (a, -1)):
            if team in played_yesterday:
                if sign > 0:
                    hf, ha = hf - B2B, ha + B2B
                else:
                    af, aa = af - B2B, aa + B2B
        start = g.get("startTimeUTC", "")[:16]
        dfo = next((v for (hn, an), v in goalies.items()
                    if LIVESPORT_NAMES[h].split()[0] in hn and LIVESPORT_NAMES[a].split()[0] in an), None)
        hg = dfo["homeGoalieName"] if dfo else "?"
        ag = dfo["awayGoalieName"] if dfo else "?"
        hgs, ags = ratings.goalie(hg), ratings.goalie(ag)
        L = ratings.league
        lh = BASE_H * (hf / L) * (aa / L) - ags * BASE_H / L
        la = BASE_A * (af / L) * (ha / L) - hgs * BASE_A / L
        ft = score_dist(lh, la)
        p1 = period_dist(lh * P1_SHARE, la * P1_SHARE)

        ev_id = next((e["AA"] for e in events
                      if LIVESPORT_NAMES[h] in e["AE"] and LIVESPORT_NAMES[a] in e["AF"]
                      and e.get("AB") == "1"), None)
        print(f"\n### {a} @ {h}  ({start} UTC)  B2B: {', '.join(t for t in (h, a) if t in played_yesterday) or '-'}")
        print(f"    brankáři: {hg} ({dfo['homeNewsStrengthName'] if dfo else '?'}, GSAx/60 {hgs:+.2f}) "
              f"vs {ag} ({dfo['awayNewsStrengthName'] if dfo else '?'}, GSAx/60 {ags:+.2f})")
        mean_total = sum((i + j) * p for (i, j), p in ft.items())
        ph = sum(p for (i, j), p in ft.items() if i > j)
        px = sum(p for (i, j), p in ft.items() if i == j)
        print(f"    model 60 min: {h} {ph*100:.1f} % | remíza {px*100:.1f} % | {a} {(1-ph-px)*100:.1f} %"
              f" | očekávané góly {mean_total:.2f}")
        if not ev_id:
            print("    kurzy nenalezeny")
            continue
        rows = odds_rows(ev_id)
        fair = market_fair_odds(rows)
        best = {}
        for r in rows:
            if r[:4] in fair and (r[:4] not in best or r[5] > best[r[:4]][1]):
                best[r[:4]] = (r[4], r[5])
        found = []
        for key, (book, odds) in best.items():
            prob = model_prob(key, ft, p1)
            if prob is None:
                continue
            ev = W_MODEL * expected_return(prob, odds) + (1 - W_MODEL) * odds / fair[key]
            if ev >= EV_MIN:
                found.append((ev, expected_return(prob, odds), odds / fair[key], key, book, odds))
        for ev, evm, evk, key, book, odds in sorted(found, reverse=True):
            print(f"    EV {ev:.3f} (model {evm:.3f}, trh {evk:.3f}) | {label(key, h, a):46} @ {odds:.2f} {book}")
        if not found:
            print("    bez value")


if __name__ == "__main__":
    main()
