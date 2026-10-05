"""Daily value scan for a league.

Usage: python3 -m hockey.scan shl 2026-10-01 [--all]
  --all  print every priced selection, not only those with EV >= 1.03
"""
import collections
import datetime
import math
import sys

from .leagues import LEAGUES, is_regular, params
from .livesport import TZ, load_league, odds_rows
from .markets import kelly_quarter, label, scan
from .model import Ratings, calibrate_shape, league_profile, period_dist, pmf, score_dist

EV_MIN = 1.03


def p1_tie_factor(profile):
    """Tie inflation that makes an average 1st period match the league's 1st-period tie rate."""
    lh = profile["home_60"] * profile["period_share"][0]
    la = profile["away_60"] * profile["period_share"][0]
    tm = sum(pmf(i, lh) * pmf(i, la) for i in range(10))
    return profile["p1_tie"] / tm


def analyse(key, date, show_all=False, out=print):
    cfg = LEAGUES[key]
    current, matches = load_league(key, cfg["path"], seasons=("2025-2026", "2024-2025"))
    regular = [m for m in matches if is_regular(m)]
    day = datetime.date.fromisoformat(date)
    games = [e for e in current if e["status"] == "1"
             and datetime.datetime.fromtimestamp(e["start"], TZ).date() == day]
    out(f"\n## {cfg['name']} — {date}: {len(games)} zápas(ů)")
    if not games:
        return []
    now = min(g["start"] for g in games)
    prm = params(key)
    ratings = Ratings(matches, now=now, **prm)
    shape, adj = calibrate_shape(regular)
    prof = league_profile([m for m in regular if m.get("season") != "2024-2025"])
    ot_home = 0.5 + 0.5 * (prof["ot_home"] - 0.5)          # regress OT home share halfway to 50 %
    p1_share = prof["period_share"][0]
    p1_tie = p1_tie_factor(prof)
    out(f"Profil ligy (2025/26 + letos): {prof['goals_60']:.2f} gólů/60 min, třetiny "
        + " / ".join(f"{100*s:.0f} %" for s in prof["period_share"])
        + f", remízy po 60 min {100*prof['tie_60']:.1f} %, vedoucí po 2. třetině nevyhraje v 60 min "
        f"{100*prof['lead_after_2_lost']:.0f} %, domácí v prodl./SN {100*prof['ot_home']:.0f} %")
    played = collections.Counter(t for m in matches if m.get("season") == "current" for t in (m["home"], m["away"]))
    picks = []
    for g in sorted(games, key=lambda e: e["start"]):
        lh, la = ratings.expected_goals(g["home"], g["away"])
        ft = score_dist(lh * adj, la * adj, shape)
        p1 = period_dist(lh * p1_share, la * p1_share, tie=p1_tie)
        h = sum(p for (i, j), p in ft.items() if i > j)
        x = sum(p for (i, j), p in ft.items() if i == j)
        start = datetime.datetime.fromtimestamp(g["start"], TZ).strftime("%H:%M")
        out(f"\n### {start} {g['home']} – {g['away']}")
        out(f"model: λ {lh:.2f} : {la:.2f} (celkem {lh+la:.2f}) | 60 min 1/X/2 = "
            f"{100*h:.1f} / {100*x:.1f} / {100*(1-h-x):.1f} %")
        try:
            rows = odds_rows(g["id"])
        except Exception as exc:  # odds not published yet
            out(f"kurzy nedostupné ({exc})")
            continue
        res = scan(rows, ft, p1, ot_home, cfg["w_model"])
        tip = {r[:4]: r[5] for r in rows if r[4] == "Tipsport.cz"}
        mk = {o["key"]: o for o in res}
        k1 = [("HOME_DRAW_AWAY", "FULL_TIME", s, None) for s in "1X2"]
        if all(k in mk for k in k1):
            out("trh (bez marže) 1/X/2 = " + " / ".join(f"{100*mk[k]['p_market']:.1f}" for k in k1) + " %")
        shown = [o for o in res if show_all or o["ev"] >= EV_MIN]
        for o in shown:
            stake = kelly_quarter(o["ev"], o["odds"])
            out(f"  EV {o['ev']:.3f} | {label(o['key'], g['home'], g['away']):46} @ {o['odds']:.2f} {o['book']:12}"
                f" (Tipsport {tip.get(o['key'], '-')}) | model {100*o['p_model']:.1f} % trh {100*o['p_market']:.1f} %"
                f" | value od {o['min_odds']:.2f} | ¼K {100*stake:.1f} %")
            if o["ev"] >= EV_MIN:
                picks.append(dict(o, league=key, game=f"{g['home']} – {g['away']}", start=start,
                                  label=label(o["key"], g["home"], g["away"]), stake=stake,
                                  n_games=min(played[g["home"]], played[g["away"]])))
        if not shown:
            out("  bez value")
    return picks


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    analyse(args[0], args[1], show_all="--all" in sys.argv)
