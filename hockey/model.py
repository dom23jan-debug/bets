"""Team ratings and score distributions for hockey leagues.

Ratings: weighted, ridge-penalised Poisson regression (attack/defence + home advantage) fitted twice,
on regulation goals and on shots on goal; the shot model is converted to goals with the league
shooting percentage and blended with the goal model (shots stabilise much faster than goals).
Weights decay exponentially with age and previous-season matches get an extra offseason discount.

Score distribution: Poisson with tie inflation + late-game goalie-pull phase (empty-net goals,
late equalisers), calibrated per league on its own margin/total distribution.
"""
import collections
import math

import numpy as np
from scipy.optimize import minimize

DAY = 86400
LEAGUE_HALF_LIFE = 120   # days, for the league-wide scoring level
NEW_TEAM_PRIOR = -0.08   # log-rate prior for attack and defence of promoted teams


class Ratings:
    def __init__(self, matches, now, half_life=180, offseason=0.6, ridge=6.0, shot_weight=0.5, total_k=1.0,
                 current="current", shot_key="sog"):
        self.now, self.hl, self.off, self.ridge, self.ws = now, half_life, offseason, ridge, shot_weight
        self.total_k, self.current = total_k, current
        teams = sorted({m["home"] for m in matches} | {m["away"] for m in matches})
        self.idx = {t: i for i, t in enumerate(teams)}
        self.n = len(teams)
        cur = [m for m in matches if m.get("season") == current]
        prev = [m for m in matches if m.get("season") != current]
        # summer break does not age the data: previous-season matches are aged in "hockey days"
        self.gap = 0.0
        if cur and prev:
            self.gap = max(0.0, min(m["start"] for m in cur) - max(m["start"] for m in prev) - 7 * DAY)
        # promoted / new teams (no previous-season data) start below average
        last_prev = max(prev, key=lambda m: m["start"])["season"] if prev else None
        prev_teams = {t for m in prev if m.get("season") == last_prev for t in (m["home"], m["away"])}
        self.prior = np.array([NEW_TEAM_PRIOR if (prev_teams and t not in prev_teams) else 0.0 for t in teams])
        self.weights = np.array([self._weight(m) for m in matches])
        self.matches = matches
        h = np.array([self.idx[m["home"]] for m in matches])
        a = np.array([self.idx[m["away"]] for m in matches])
        rg = np.array([[sum(p[0] or 0 for p in m["periods"]), sum(p[1] or 0 for p in m["periods"])]
                       for m in matches], float)
        self.goal = self._fit(h, a, rg[:, 0], rg[:, 1], self.weights)
        hk, ak = "h_" + shot_key, "a_" + shot_key
        has = np.array([hk in m for m in matches])
        if has.sum() > 30:
            sog = np.array([[m.get(hk, 0), m.get(ak, 0)] for m in matches], float)
            self.shot = self._fit(h[has], a[has], sog[has, 0], sog[has, 1], self.weights[has])
            w = self.weights[has]
            self.sh_pct = (w * rg[has].sum(1)).sum() / (w * sog[has].sum(1)).sum()
        else:
            self.shot = None
        # league scoring level: longer window than team ratings (totals need a stable mean)
        lw = np.array([0.5 ** (max(0.0, (now - m["start"]) / DAY) / LEAGUE_HALF_LIFE) for m in matches])
        self.league_home = (lw * rg[:, 0]).sum() / lw.sum()
        self.league_away = (lw * rg[:, 1]).sum() / lw.sum()
        self.current_teams = {m["home"] for m in cur} | {m["away"] for m in cur} or set(teams)

    def _weight(self, m):
        age = self.now - m["start"]
        if m.get("season") != self.current:
            age -= self.gap
        w = 0.5 ** (max(0.0, age / DAY) / self.hl)
        if m.get("season") != self.current:
            w *= self.off
        return w

    def _fit(self, h, a, yh, ya, w):
        n, pr = self.n, self.prior

        def nll(x):
            mu, hfa, att, de = x[0], x[1], x[2:2 + n], x[2 + n:]
            lh = np.exp(mu + hfa + att[h] - de[a])
            la = np.exp(mu + att[a] - de[h])
            ll = (w * (yh * np.log(lh) - lh + ya * np.log(la) - la)).sum()
            ra, rd = att - pr, de - pr
            pen = self.ridge * np.exp(mu) * ((ra ** 2).sum() + (rd ** 2).sum())
            gmu = (w * (yh - lh + ya - la)).sum()
            ghfa = (w * (yh - lh)).sum()
            gatt = np.bincount(h, w * (yh - lh), n) + np.bincount(a, w * (ya - la), n)
            gde = -np.bincount(a, w * (yh - lh), n) - np.bincount(h, w * (ya - la), n)
            c = 2 * self.ridge * np.exp(mu)
            grad = np.concatenate([[gmu - pen], [ghfa], gatt - c * ra, gde - c * rd])
            return -(ll - pen), -grad

        x0 = np.zeros(2 + 2 * n)
        x0[0] = math.log(max(0.1, (w * (yh + ya)).sum() / (2 * w.sum())))
        res = minimize(nll, x0, jac=True, method="L-BFGS-B")
        x = res.x
        return {"mu": x[0], "hfa": x[1], "att": x[2:2 + n], "def": x[2 + n:]}

    def _rate(self, model, home, away):
        i, j = self.idx.get(home), self.idx.get(away)
        ai = model["att"][i] if i is not None else -0.08
        di = model["def"][i] if i is not None else -0.08
        aj = model["att"][j] if j is not None else -0.08
        dj = model["def"][j] if j is not None else -0.08
        lh = math.exp(model["mu"] + model["hfa"] + ai - dj)
        la = math.exp(model["mu"] + aj - di)
        return lh, la

    def expected_goals(self, home, away):
        """Expected 60-min goals. Team ratings set the split (strength); the match total is shrunk
        toward the league average by total_k (team-specific totals are mostly noise)."""
        gh, ga = self._rate(self.goal, home, away)
        if self.shot and self.ws > 0:
            sh, sa = self._rate(self.shot, home, away)
            sh, sa = sh * self.sh_pct, sa * self.sh_pct
            gh = math.exp(self.ws * math.log(sh) + (1 - self.ws) * math.log(gh))
            ga = math.exp(self.ws * math.log(sa) + (1 - self.ws) * math.log(ga))
        total, league = gh + ga, self.league_home + self.league_away
        target = league + self.total_k * (total - league)
        return gh * target / total, ga * target / total

    def table(self):
        rows = []
        for t, i in self.idx.items():
            if t not in self.current_teams:
                continue
            g = (self.goal["att"][i], self.goal["def"][i])
            s = (self.shot["att"][i], self.shot["def"][i]) if self.shot else (0, 0)
            rows.append((t, g[0] + g[1], g[0], g[1], s[0] + s[1]))
        return sorted(rows, key=lambda r: -r[1])


# ----------------------------------------------------------------------------- score distribution
def pmf(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


DEFAULT_SHAPE = {"late": 0.06, "en_lead": 0.45, "en_second": 0.25, "late_eq": 0.25, "tie": 1.2}


def score_dist(lh, la, shape=DEFAULT_SHAPE, n=15):
    late = shape["late"]
    mh, ma = lh * (1 - late), la * (1 - late)
    base = {(i, j): pmf(i, mh) * pmf(j, ma) for i in range(n) for j in range(n)}
    tie_mass = sum(v for (i, j), v in base.items() if i == j)
    tie = min(shape["tie"], 0.95 / tie_mass)
    dist = collections.defaultdict(float)
    en, en2, eq = shape["en_lead"], shape["en_second"], shape["late_eq"]
    for (i, j), p in base.items():
        p *= tie if i == j else (1 - tie_mass * tie) / (1 - tie_mass)
        d = i - j
        if abs(d) in (1, 2):
            none = 1 - en - eq
            if d > 0:
                moves = (((0, 1), eq), ((1, 0), en * (1 - en2)), ((2, 0), en * en2), ((0, 0), none))
            else:
                moves = (((1, 0), eq), ((0, 1), en * (1 - en2)), ((0, 2), en * en2), ((0, 0), none))
            for (dx, dy), q in moves:
                dist[(i + dx, j + dy)] += p * q
        else:
            for x in range(4):
                for y in range(4):
                    dist[(i + x, j + y)] += p * pmf(x, lh * late) * pmf(y, la * late)
    return dist


def period_dist(lh, la, tie=1.0, n=10):
    base = {(i, j): pmf(i, lh) * pmf(j, la) for i in range(n) for j in range(n)}
    tm = sum(v for (i, j), v in base.items() if i == j)
    tie = min(tie, 0.95 / tm)
    return {(i, j): v * (tie if i == j else (1 - tm * tie) / (1 - tm)) for (i, j), v in base.items()}


def regulation(m):
    return sum(p[0] or 0 for p in m["periods"]), sum(p[1] or 0 for p in m["periods"])


def calibrate_shape(matches):
    """Grid-fit the late-game/tie shape to the league's regulation margin and total distribution."""
    reg = [regulation(m) for m in matches]
    n = len(reg)
    emp_m = collections.Counter(max(-5, min(5, h - a)) for h, a in reg)
    emp_t = collections.Counter(min(11, h + a) for h, a in reg)
    lh0 = sum(h for h, _ in reg) / n
    la0 = sum(a for _, a in reg) / n
    best = None
    for en in (0.25, 0.4, 0.55, 0.7):
        for en2 in (0.15, 0.3):
            for eq in (0.15, 0.25, 0.35):
                for tie in (1.0, 1.15, 1.3, 1.45):
                    shape = {"late": 0.06, "en_lead": en, "en_second": en2, "late_eq": eq, "tie": tie}
                    # base rates shrink a bit because the EN phase adds goals
                    adj = 1 - 0.04 * en
                    mix = collections.defaultdict(float)
                    for s in (-0.3, 0.0, 0.3):
                        for k, v in score_dist(lh0 * adj * math.exp(s / 2), la0 * adj * math.exp(-s / 2),
                                               shape).items():
                            mix[k] += v / 3
                    m = collections.Counter()
                    t = collections.Counter()
                    for (i, j), v in mix.items():
                        m[max(-5, min(5, i - j))] += v
                        t[min(11, i + j)] += v
                    err = (sum((m[k] - emp_m[k] / n) ** 2 for k in range(-5, 6))
                           + sum((t[k] - emp_t[k] / n) ** 2 for k in range(12)))
                    if best is None or err < best[0]:
                        best = (err, shape, adj)
    return best[1], best[2]


def league_profile(matches):
    """Descriptive league profile: scoring by period, ties, OT home share, comebacks."""
    reg = [regulation(m) for m in matches]
    n = len(matches)
    per = [[0, 0, 0] for _ in range(1)]
    totals = [0.0, 0.0, 0.0]
    p1_tie = 0
    for m in matches:
        for k in range(3):
            totals[k] += (m["periods"][k][0] or 0) + (m["periods"][k][1] or 0)
        p1_tie += (m["periods"][0][0] or 0) == (m["periods"][0][1] or 0)
    ot = [m for m, (h, a) in zip(matches, reg) if h == a]
    ot_home = sum((m["home_goals"] or 0) > (m["away_goals"] or 0) for m in ot) / max(1, len(ot))
    # comebacks: leader after 2 periods does not win in regulation
    lead2 = comeback2 = 0
    for m in matches:
        h2 = sum(p[0] or 0 for p in m["periods"][:2])
        a2 = sum(p[1] or 0 for p in m["periods"][:2])
        h, a = regulation(m)
        if h2 != a2:
            lead2 += 1
            if (h2 > a2 and h <= a) or (a2 > h2 and a <= h):
                comeback2 += 1
    g = sum(totals)
    return {
        "matches": n,
        "goals_60": g / n,
        "home_60": sum(h for h, _ in reg) / n,
        "away_60": sum(a for _, a in reg) / n,
        "period_share": [t / g for t in totals],
        "period_goals": [t / n for t in totals],
        "tie_60": sum(h == a for h, a in reg) / n,
        "p1_tie": p1_tie / n,
        "ot_home": ot_home,
        "lead_after_2_lost": comeback2 / max(1, lead2),
        "home_win_60": sum(h > a for h, a in reg) / n,
    }
