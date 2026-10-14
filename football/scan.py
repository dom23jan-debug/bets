"""Daily value scan of one football league.

Usage: python3 -m football.scan eng1 2026-10-17 [--all] [--no-extra]
  --all       print every priced selection, not only candidates
  --no-extra  skip Fortuna statistics markets and Sofascore (referee, bet365 corner/card lines, injuries)

Per offer of a Czech bookmaker (Tipsport, Fortuna, Chance, Betano):
  EV trh    - vs. the consensus of ~30-60 international books (margin removed, sharper books weigh more);
              markets the international books do not list are priced from goal expectancies implied by the
              consensus 1X2 + totals ("trh*"), corners / cards from the bet365 line on Sofascore
  EV model  - own ratings (goals + xG, Dixon-Coles) and count models for corners, cards, shots, fouls ...
Tier (backtest 2025/26, see skill football-value):
  A  direct consensus, full-time main market, EV trh >= 1.02, EV model >= 1.0, odds 1.5-3.2
     (A! = EV trh > 1.06: check the price still exists and the news - big gaps are often stale lines)
     outside leagues.EARLY_OK only within LATE_HOURS of kick-off, earlier it is "AP" (re-scan later)
  B  direct consensus for other goal markets (halves, European handicap ...): EV trh >= 1.04, model >= 1.0
     (prices implied from the consensus 1X2 + totals - "trh*", e.g. Fortuna team totals - are shown with
     --all but never a tier: they lost in the 2025/26 backtest)
  C  match totals of corners / yellow cards vs the bet365 line: EV trh >= 1.05, EV model >= 1.0, odds <= 3.2
     (experimental; team corners / "more corners" lean on our model split -> no tier)
  S  "sledovat": model-only corners / cards markets (team corners, more corners, team cards) with EV model
     >= 1.15 - logged to journal/rejected.csv to learn, never on the ticket. Shots / fouls / offsides: no tier
     at all (Fortuna counts shots differently from Livesport/Opta, its lines are ~10 % higher)
  -  everything else is not a candidate
"""
import concurrent.futures as cf
import datetime
import math
import sys
import time

import numpy as np
from scipy.optimize import minimize

from . import fortuna, sofascore
from .leagues import EARLY_OK, LEAGUES, is_regular, params
from .livesport import TZ, load_league, multi_geo_rows, odds_rows, participants
from .markets import consensus, expected_return, htft, kelly_stake, label, model_prob, scan, win_prob
from .model import (GoalModel, StatModels, fit_rho, half_dist, half_tie_factor, league_profile, nb_pmf,
                    score_dist)

INTL_GEOS = ("SE", "KR", "GB")
MAIN = ("HOME_DRAW_AWAY", "DOUBLE_CHANCE", "DRAW_NO_BET", "ASIAN_HANDICAP", "OVER_UNDER", "BOTH_TEAMS_TO_SCORE")
TIERS = {"A": {"ev": 1.02, "odds": (1.5, 3.2), "cap": 0.02}, "B": {"ev": 1.04, "odds": (1.01, 3.2), "cap": 0.005},
         "C": {"ev": 1.05, "odds": (1.01, 3.2), "cap": 0.005}}
SUSPICIOUS = 1.06
LATE_HOURS = 3.0        # outside EARLY_OK leagues tier A needs kick-off within this many hours ("AP" = later)
TICKET_TIERS = ("A", "A!", "B", "B!", "C", "C!")
WATCH_EV = 1.15         # model-only statistics edge worth logging ("S" = sledovat, never on the ticket)
# Fortuna's shots / shots-on-target lines sit ~10 % above Livesport (Opta) counts (Oct 2026: main lines 26.5-29.5
# vs league means 24.6-26.5) -> different counting, model "unders" are artefacts; fouls / offsides likewise
# unverified. Only corners and cards are counted the same way everywhere.
WATCH_STATS = ("cor", "yc", "cards")
N_MAX = 70
STAT_RIDGE = 8.0        # count models: strong shrinkage beat weak shrinkage for match totals (2025/26 backtest)


class LeagueContext:
    """Everything fitted once per league and date."""

    def __init__(self, key, date):
        self.key, self.cfg = key, LEAGUES[key]
        self.current, matches = load_league(key, self.cfg["path"], self.cfg["seasons"])
        day = datetime.date.fromisoformat(date)
        self.games = sorted([e for e in self.current if e["status"] == "1"
                             and datetime.datetime.fromtimestamp(e["start"], TZ).date() == day],
                            key=lambda e: e["start"])
        if not self.games:
            return
        now = min(g["start"] for g in self.games)
        hist = [m for m in matches if m["start"] < now and m.get("home_goals") is not None]
        self.prm = params(key)
        self.gm = GoalModel(hist, now, **self.prm)
        self.stats = StatModels(hist, self.gm.weights, ridge=self.prm.get("stat_ridge", STAT_RIDGE))
        regular = [m for m in hist if is_regular(m)]
        recent = regular[-700:]
        self.prof = league_profile(recent)
        self.rho = fit_rho(recent[-400:], self.gm) if len(recent) > 100 else -0.06
        self.played = {}
        for m in hist:
            if m.get("season") == "current":
                for t in (m["home"], m["away"]):
                    self.played[t] = self.played.get(t, 0) + 1
        self.model_filter = self.cfg.get("model_filter", True)

    def goal_ctx(self, lh, la):
        s1 = self.prof.get("h1_share", 0.45)
        t1 = half_tie_factor(self.prof, lh, la, 1)
        t2 = half_tie_factor(self.prof, lh, la, 2)
        h1 = half_dist(lh * s1, la * s1, t1)
        h2 = half_dist(lh * (1 - s1), la * (1 - s1), t2)
        return {"ft": score_dist(lh, la, self.rho), "h1": h1, "h2": h2, "htft": htft(h1, h2), "stats": {},
                "lambda": (lh, la)}

    def stat_ctx(self, ctx, home, away, ref_factor=None):
        for st, r in self.stats.models.items():
            mu_h, mu_a = r.rates(home, away)
            if st in ("yc", "cards") and ref_factor:
                mu_h, mu_a = mu_h * ref_factor, mu_a * ref_factor
            kt, kk = self.stats.k_team[st], self.stats.k_total[st]
            ctx["stats"][(st, "FULL_TIME")] = {"h": nb_pmf(N_MAX, mu_h, kt), "a": nb_pmf(N_MAX, mu_a, kt),
                                               "t": nb_pmf(N_MAX, mu_h + mu_a, kk), "mu": (mu_h, mu_a)}
            s = self.stats.half_share.get(st)
            if s:
                ctx["stats"][(st, "FIRST_HALF")] = {"h": nb_pmf(N_MAX, mu_h * s, kt), "a": nb_pmf(N_MAX, mu_a * s, kt),
                                                    "t": nb_pmf(N_MAX, (mu_h + mu_a) * s, kk), "mu": (mu_h * s, mu_a * s)}
        return ctx


def implied_lambdas(cons, rho):
    """Goal expectancies that reproduce the consensus 1X2 and full-time totals (x.5 lines)."""
    target = []
    for sel in ("1", "X", "2"):
        c = cons.get(("HOME_DRAW_AWAY", "FULL_TIME", sel, None))
        if c:
            target.append((("HOME_DRAW_AWAY", "FULL_TIME", sel, None), c[0], 1.0))
    for key, (p, n) in cons.items():
        if key[0] == "OVER_UNDER" and key[1] == "FULL_TIME" and key[2] == "OVER" and (key[3] * 2) % 2 == 1:
            target.append((key, p, 1.0 if abs(key[3] - 2.5) < 1.1 else 0.5))
    if len(target) < 3:
        return None

    def loss(x):
        lh, la = math.exp(x[0]), math.exp(x[1])
        ctx = {"ft": score_dist(lh, la, rho)}
        return sum(w * (model_prob(k, ctx)[0] - p) ** 2 for k, p, w in target)

    res = minimize(loss, np.log([1.4, 1.1]), method="Nelder-Mead", options={"xatol": 1e-4, "fatol": 1e-9})
    return math.exp(res.x[0]), math.exp(res.x[1])


def implied_mean(pmf_fn, line, p_over, k):
    """Mean of a negative binomial with P(X > line) = p_over (bisection)."""
    lo, hi = 0.2, 60.0
    for _ in range(50):
        mid = (lo + hi) / 2
        pm = pmf_fn(mid, k)
        if sum(pm[int(math.floor(line)) + 1:]) < p_over:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def referee_factor(ref, league_yc):
    """Card multiplier of the appointed referee (career yellows per game vs league), shrunk to 1."""
    if not ref or not ref["games"] or not league_yc:
        return None
    ypg = (ref["yellow"] + ref["yellow_red"]) / ref["games"]
    k = 30
    return ((ypg * ref["games"] + league_yc * k) / (ref["games"] + k)) / league_yc


def market_stat_ctx(lc, ctx, b365):
    """Market-implied corner / card distributions from bet365 main lines (same dispersion as the model)."""
    out = {}
    for (name, line), d in b365.items():
        st = {"cor": "cor", "cards": "cards"}.get(name)
        if not st or (st, "FULL_TIME") not in ctx["stats"]:
            continue
        o, u = d["OVER"][1], d["UNDER"][1]
        p_over = (1 / o) / (1 / o + 1 / u)
        kk = lc.stats.k_total[st]
        mu = implied_mean(lambda m, k: nb_pmf(N_MAX, m, k), line, p_over, kk)
        mh, ma = ctx["stats"][(st, "FULL_TIME")]["mu"]
        sh = mh / (mh + ma)
        kt = lc.stats.k_team[st]
        out[(st, "FULL_TIME")] = {"h": nb_pmf(N_MAX, mu * sh, kt), "a": nb_pmf(N_MAX, mu * (1 - sh), kt),
                                  "t": nb_pmf(N_MAX, mu, kk), "mu": (mu * sh, mu * (1 - sh)), "line": (line, p_over)}
        if st == "cards" and ("yc", "FULL_TIME") in ctx["stats"]:
            # yellow-card markets (Fortuna) from the cards line: same market level, model's yellow share
            yh, ya = ctx["stats"][("yc", "FULL_TIME")]["mu"]
            r = (yh + ya) / (mh + ma)
            ky, kyt = lc.stats.k_total["yc"], lc.stats.k_team["yc"]
            out[("yc", "FULL_TIME")] = {"h": nb_pmf(N_MAX, mu * r * sh, kyt), "a": nb_pmf(N_MAX, mu * r * (1 - sh), kyt),
                                        "t": nb_pmf(N_MAX, mu * r, ky), "mu": (mu * r * sh, mu * r * (1 - sh)),
                                        "line": (line, p_over)}
    return out


def analyse_game(lc, g, extra=True):
    home, away = g["home"], g["away"]
    lh, la = lc.gm.expected_goals(home, away)
    ctx = lc.goal_ctx(lh, la)
    info = {"lambda": (lh, la), "notes": []}
    try:
        parts = participants(g["id"])
        rows = odds_rows(g["id"], "CZ", parts)
        intl = multi_geo_rows(g["id"], INTL_GEOS, parts)
    except Exception as exc:
        info["error"] = f"kurzy nedostupné ({exc})"
        return ctx, None, [], info
    cons = consensus(rows + intl)
    info["n_books"] = len({r[4] for r in intl})
    mk = implied_lambdas(cons, lc.rho)
    mctx = lc.goal_ctx(*mk) if mk else None
    info["market_lambda"] = mk
    ref, b365, sofa_id = None, {}, None
    f_rows = []
    if extra:
        f_rows, fx = fortuna.rows_for(lc.cfg.get("fortuna"), g["start"], home, away)
        if lc.cfg.get("sofa"):
            try:
                ev = sofascore.find_event(lc.cfg["sofa"], g["start"], home, away)
                sofa_id = ev["id"] if ev else None
                if sofa_id:
                    ref = sofascore.referee(sofa_id)
                    b365 = sofascore.bet365_lines(sofa_id)
            except Exception as exc:
                info["notes"].append(f"sofascore: {exc}")
    rf = referee_factor(ref, lc.prof.get("yc"))
    info["referee"] = (ref, rf)
    info["sofa_id"] = sofa_id
    lc.stat_ctx(ctx, home, away, rf)
    if mctx is not None:
        lc.stat_ctx(mctx, home, away, rf)
        mctx["stats"].update(market_stat_ctx(lc, ctx, b365))
        info["b365"] = {k: v for k, v in b365.items() if k[0] in ("cor", "cards")}
    res = scan(rows + f_rows, cons, ctx)
    for o in res:
        key = o["key"]
        stat = key[0].split(":")[1] if ":" in key[0] else None
        if o["ev_market"] is None and mctx is not None:
            prob_m = model_prob(key, mctx)
            has_line = (stat, key[1]) in mctx["stats"] and "line" in mctx["stats"][(stat, key[1])]
            if prob_m is not None and (stat in (None, "goals") or has_line):
                o["ev_market"] = o["ev"] = expected_return(prob_m, o["odds"])
                o["p_market"] = win_prob(prob_m)
                o["implied"] = True
        o["source"] = ("jen model" if o["ev_market"] is None else
                       ("trh*" if o.get("implied") else "trh"))
        o["tier"] = tier(o, stat, lc.model_filter)
        if o["tier"] in ("A", "A!") and lc.key not in EARLY_OK and (g["start"] - time.time()) / 3600 > LATE_HOURS:
            o["tier"] = "AP"           # second tiers / untested leagues: re-check ~2 h before kick-off
        if o["tier"] is None and stat in WATCH_STATS and o["ev_model"] >= WATCH_EV and 1.4 <= o["odds"] <= 3.2 \
                and 0.3 <= o["p_model"] <= 0.75:
            o["tier"] = "S"
        need = TIERS[o["tier"].rstrip("!")]["ev"] if o["tier"] in TICKET_TIERS else TIERS["A"]["ev"]
        o["min_odds"] = o["odds"] * need / o["ev"] if o["ev"] > 0 else None
        o["stake"] = (kelly_stake(o["ev"], o["odds"], TIERS[o["tier"].rstrip("!")]["cap"])
                      if o["tier"] in TICKET_TIERS else 0.0)
    order = {"A": 0, "A!": 0, "AP": 1, "B": 2, "B!": 2, "C": 3, "C!": 3, "S": 4}
    res.sort(key=lambda o: (order.get(o["tier"], 9), -o["ev"]))
    return ctx, cons, res, info


def tier(o, stat, model_filter=True):
    """Candidate tier of an offer (see module docstring) or None."""
    if o["ev_market"] is None:
        return None
    bt, scope = o["key"][0], o["key"][1]
    # the model must agree; cups skip that only for goal markets (cross-league ratings), never for statistics
    if (model_filter or stat is not None) and o["ev_model"] < 1.0:
        return None
    if stat is None and not o.get("implied") and bt in MAIN and scope == "FULL_TIME" and o["n_books"] >= 3:
        t = "A"
    elif stat is None and not o.get("implied") and o["n_books"] >= 3:
        t = "B"            # direct consensus, other goal markets (halves, European handicap, HT/FT ...)
    elif stat in ("cor", "yc", "cards") and bt.startswith("TOTAL:"):
        t = "C"            # match totals only: the bet365 line is a real market reference there
    else:
        return None
    lo, hi = TIERS[t]["odds"]
    if o["ev_market"] < TIERS[t]["ev"] or not lo <= o["odds"] <= hi:
        return None
    return t + "!" if o["ev_market"] > SUSPICIOUS else t


def analyse(key, date, show_all=False, extra=True, out=print):
    lc = LeagueContext(key, date)
    out(f"\n## {lc.cfg['name']} — {date}: {len(lc.games)} zápas(ů)")
    if not lc.games:
        return []
    p = lc.prof
    out(f"Profil ligy: {p['goals']:.2f} gólu/zápas (1. poločas {100*p['h1_share']:.0f} %), domácí výhra "
        f"{100*p['home_win']:.0f} %, remíza {100*p['draw']:.0f} %, nad 2.5 {100*p['over25']:.0f} %, BTTS "
        f"{100*p['btts']:.0f} %" + "".join(f", {n} {p[k]:.1f}" for k, n in (("cor", "rohy"), ("yc", "ŽK"),
                                                                              ("sh", "střely"), ("fo", "fauly"))
                                          if k in p) + f" | DC rho {lc.rho:+.2f}")
    picks = []
    with cf.ThreadPoolExecutor(6) as ex:
        results = list(ex.map(lambda g: analyse_game(lc, g, extra), lc.games))
    for g, (ctx, cons, res, info) in zip(lc.games, results):
        start = datetime.datetime.fromtimestamp(g["start"], TZ).strftime("%H:%M")
        lh, la = info["lambda"]
        ft = ctx["ft"]
        h = sum(v for (i, j), v in ft.items() if i > j)
        x = sum(v for (i, j), v in ft.items() if i == j)
        out(f"\n### {start} {g['home']} – {g['away']}")
        line = f"model: λ {lh:.2f} : {la:.2f} | 1/X/2 {100*h:.0f} / {100*x:.0f} / {100*(1-h-x):.0f} %"
        if info.get("market_lambda"):
            mh, ma = info["market_lambda"]
            line += f" | trh: λ {mh:.2f} : {ma:.2f}"
        if cons:
            k1 = [("HOME_DRAW_AWAY", "FULL_TIME", s, None) for s in "1X2"]
            if all(k in cons for k in k1):
                line += " = " + " / ".join(f"{100*cons[k][0]:.0f}" for k in k1) + f" % ({info.get('n_books', 0)} zahr. kanceláří)"
        out(line)
        if "error" in info:
            out("  " + info["error"])
            continue
        ref, rf = info.get("referee") or (None, None)
        st = ctx["stats"]
        extra_line = []
        for s, n in (("cor", "rohy"), ("yc", "ŽK"), ("sh", "střely"), ("sot", "na branku")):
            if (s, "FULL_TIME") in st:
                a, b = st[(s, "FULL_TIME")]["mu"]
                extra_line.append(f"{n} {a:.1f}:{b:.1f}")
        if ref:
            ypg = (ref["yellow"] + ref["yellow_red"]) / max(1, ref["games"])
            extra_line.append(f"rozhodčí {ref['name']} ({ref['games']} z., {ypg:.1f} ŽK/z."
                              + (f", faktor karet {rf:.2f})" if rf else ")"))
        for (s, ln), d in (info.get("b365") or {}).items():
            extra_line.append(f"bet365 {s} {ln:g}: více {d['OVER'][1]:.2f} / méně {d['UNDER'][1]:.2f}")
        if extra_line:
            out("  " + " | ".join(extra_line))
        ngames = min(lc.played.get(g["home"], 0), lc.played.get(g["away"], 0))
        shown = [o for o in res if show_all or o["tier"]]
        for o in shown[: (None if show_all else 8)]:
            pm = f"{100*o['p_market']:.1f} %" if o["p_market"] is not None else "–"
            evm = f"{o['ev_market']:.3f}" if o["ev_market"] is not None else "  –  "
            out(f"  [{o['tier'] or '-':2}] EV trh {evm} model {o['ev_model']:.3f} | "
                f"{label(o['key'], g['home'], g['away']):58} @ {o['odds']:.2f} {o['book']:11} | p model "
                f"{100*o['p_model']:.1f} % {o['source']} {pm} ({o['n_books']} k.) | value od {o['min_odds']:.2f}"
                f" | vklad {100*o['stake']:.1f} %")
            if o["tier"]:
                picks.append(dict(o, league=key, game=f"{g['home']} – {g['away']}", start=start, id=g["id"],
                                  label=label(o["key"], g["home"], g["away"]), n_games=ngames,
                                  sofa_id=info.get("sofa_id")))
        if not shown:
            out("  bez value")
    return picks


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    analyse(args[0], args[1], show_all="--all" in sys.argv, extra="--no-extra" not in sys.argv)
