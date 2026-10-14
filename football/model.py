"""Team ratings and probability distributions for football.

Goals: weighted ridge Poisson regression (attack/defence + home advantage, exponential time decay, summer
break not ageing the data, previous seasons discounted, promoted teams start below average), fitted on goals
and on expected goals (xG); the two are blended in log space (xG stabilises much faster than goals).
Score distribution: Dixon-Coles corrected Poisson (low-score dependence rho per league); halves: league
share of goals per half with a half-specific draw factor.

Match statistics (corners, cards, shots, shots on target, fouls, offsides): the same regression per stat
("for" vs. "against" tendencies + home effect) with negative-binomial dispersion estimated per league.
"""
import math

import numpy as np
from scipy.optimize import minimize

DAY = 86400
LEAGUE_HALF_LIFE = 365     # days, league-wide level of a stat
NEW_TEAM_PRIOR = -0.12     # log-rate prior for attack and defence of promoted teams
STATS = {"cor": "rohy", "yc": "žluté karty", "cards": "karty (ŽK+ČK)", "sh": "střely", "sot": "střely na branku",
         "fo": "fauly", "off": "ofsajdy"}


def stat_pair(m, key, half=""):
    """(home, away) value of a stat or None; key 'goals', 'xg', 'cards' (yellow + red) or a stats key."""
    if key == "goals":
        if half == "1":
            return tuple(m["ht"]) if m.get("ht") and m["ht"][0] is not None else None
        return (m["home_goals"], m["away_goals"])
    if key == "cards":
        y = stat_pair(m, "yc", half)
        r = stat_pair(m, "rc", half)
        return (y[0] + r[0], y[1] + r[1]) if y and r else None
    hk, ak = f"h{half}_{key}", f"a{half}_{key}"
    if hk in m and ak in m:
        return (m[hk], m[ak])
    return None


class Weights:
    """Time-decay weights shared by all models of one league snapshot."""

    def __init__(self, matches, now, half_life, offseason, current="current"):
        cur = [m for m in matches if m.get("season") == current]
        prev = [m for m in matches if m.get("season") != current]
        gap = 0.0
        if cur and prev:
            gap = max(0.0, min(m["start"] for m in cur) - max(m["start"] for m in prev) - 7 * DAY)
        self.w = []
        for m in matches:
            age = now - m["start"]
            if m.get("season") != current:
                age -= gap
            w = 0.5 ** (max(0.0, age / DAY) / half_life)
            self.w.append(w * (offseason if m.get("season") != current else 1.0))
        self.w = np.array(self.w)
        last_prev = max(prev, key=lambda m: m["start"])["season"] if prev else None
        self.prev_teams = {t for m in prev if m.get("season") == last_prev for t in (m["home"], m["away"])}
        self.current_teams = {t for m in cur for t in (m["home"], m["away"])}
        self.league_w = np.array([0.5 ** (max(0.0, (now - m["start"]) / DAY) / LEAGUE_HALF_LIFE) for m in matches])


class Ratings:
    """Poisson rate model rate_home = exp(mu + hfa + att[h] - def[a]), rate_away = exp(mu + att[a] - def[h])."""

    def __init__(self, matches, weights, key, ridge, half="", new_team_prior=NEW_TEAM_PRIOR):
        teams = sorted({m["home"] for m in matches} | {m["away"] for m in matches})
        self.idx = {t: i for i, t in enumerate(teams)}
        self.n = len(teams)
        self.ridge = ridge
        prev = weights.prev_teams
        self.prior = np.array([new_team_prior if (prev and t not in prev) else 0.0 for t in teams])
        rows = [(i, stat_pair(m, key, half)) for i, m in enumerate(matches)]
        rows = [(i, p) for i, p in rows if p is not None and p[0] is not None and p[1] is not None]
        self.n_obs = len(rows)
        if self.n_obs < 30:
            self.model = None
            return
        sel = np.array([i for i, _ in rows])
        y = np.array([p for _, p in rows], float)
        h = np.array([self.idx[matches[i]["home"]] for i in sel])
        a = np.array([self.idx[matches[i]["away"]] for i in sel])
        w = weights.w[sel]
        self.model = self._fit(h, a, y[:, 0], y[:, 1], w)
        lw = weights.league_w[sel]
        self.league_home = (lw * y[:, 0]).sum() / lw.sum()
        self.league_away = (lw * y[:, 1]).sum() / lw.sum()
        # in-sample fitted rates for dispersion estimates
        mdl = self.model
        self.fit_h = np.exp(mdl["mu"] + mdl["hfa"] + mdl["att"][h] - mdl["def"][a])
        self.fit_a = np.exp(mdl["mu"] + mdl["att"][a] - mdl["def"][h])
        self.y, self.w_obs = y, w

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
        x0[0] = math.log(max(0.05, (w * (yh + ya)).sum() / (2 * w.sum())))
        res = minimize(nll, x0, jac=True, method="L-BFGS-B")
        x = res.x
        return {"mu": x[0], "hfa": x[1], "att": x[2:2 + n], "def": x[2 + n:]}

    def rates(self, home, away):
        mdl = self.model
        i, j = self.idx.get(home), self.idx.get(away)
        ai = mdl["att"][i] if i is not None else NEW_TEAM_PRIOR
        di = mdl["def"][i] if i is not None else NEW_TEAM_PRIOR
        aj = mdl["att"][j] if j is not None else NEW_TEAM_PRIOR
        dj = mdl["def"][j] if j is not None else NEW_TEAM_PRIOR
        return math.exp(mdl["mu"] + mdl["hfa"] + ai - dj), math.exp(mdl["mu"] + aj - di)

    def dispersion(self):
        """Negative-binomial size k of the match total (Var = mu + mu^2/k); inf = Poisson."""
        mu = self.fit_h + self.fit_a
        t = self.y.sum(1)
        w = self.w_obs
        excess = (w * ((t - mu) ** 2 - mu)).sum()
        if excess <= 0:
            return float("inf")
        return max(2.0, (w * mu ** 2).sum() / excess)

    def team_dispersion(self):
        mu = np.concatenate([self.fit_h, self.fit_a])
        y = np.concatenate([self.y[:, 0], self.y[:, 1]])
        w = np.concatenate([self.w_obs, self.w_obs])
        excess = (w * ((y - mu) ** 2 - mu)).sum()
        if excess <= 0:
            return float("inf")
        return max(1.5, (w * mu ** 2).sum() / excess)


class GoalModel:
    """Expected goals of a fixture from goal- and xG-based ratings."""

    def __init__(self, matches, now, half_life=240, offseason=0.7, xg_weight=0.6, ridge=2.0, total_k=0.5,
                 current="current", **_):
        self.weights = Weights(matches, now, half_life, offseason, current)
        self.goals = Ratings(matches, self.weights, "goals", ridge)
        self.xg = Ratings(matches, self.weights, "xg", ridge)
        self.wx = xg_weight if self.xg.model is not None else 0.0
        self.total_k = total_k
        self.current_teams = self.weights.current_teams

    def expected_goals(self, home, away):
        """Team ratings set the split (strength); the match total is shrunk toward the league average by
        total_k (team-specific totals are mostly noise)."""
        gh, ga = self.goals.rates(home, away)
        if self.wx > 0:
            xh, xa = self.xg.rates(home, away)
            # xG ratings measure chance quality; rescale to the league's goal level
            sh = self.goals.league_home / self.xg.league_home
            sa = self.goals.league_away / self.xg.league_away
            gh = math.exp(self.wx * math.log(xh * sh) + (1 - self.wx) * math.log(gh))
            ga = math.exp(self.wx * math.log(xa * sa) + (1 - self.wx) * math.log(ga))
        total, league = gh + ga, self.goals.league_home + self.goals.league_away
        target = league + self.total_k * (total - league)
        return gh * target / total, ga * target / total

    def table(self):
        out = []
        g = self.goals.model
        x = self.xg.model
        for t, i in self.goals.idx.items():
            if t not in self.current_teams:
                continue
            xi = self.xg.idx.get(t)
            xs = (x["att"][xi] + x["def"][xi]) if x is not None and xi is not None else float("nan")
            out.append((t, g["att"][i] + g["def"][i], g["att"][i], g["def"][i], xs))
        return sorted(out, key=lambda r: -r[1])


class StatModels:
    """Count models for match statistics (corners, cards, shots...) with per-league dispersion."""

    def __init__(self, matches, weights, ridge=2.0, keys=("cor", "cards", "yc", "sh", "sot", "fo", "off")):
        self.models, self.k_total, self.k_team, self.half_share = {}, {}, {}, {}
        for key in keys:
            r = Ratings(matches, weights, key, ridge, new_team_prior=0.0)
            if r.model is None:
                continue
            self.models[key] = r
            self.k_total[key] = r.dispersion()
            self.k_team[key] = r.team_dispersion()
            first = [stat_pair(m, key, "1") for m in matches]
            full = [stat_pair(m, key) for m in matches]
            both = [(f, a) for f, a in zip(first, full) if f and a]
            if len(both) > 30:
                self.half_share[key] = sum(f[0] + f[1] for f, _ in both) / max(1e-9, sum(a[0] + a[1] for _, a in both))

    def expected(self, key, home, away):
        return self.models[key].rates(home, away) if key in self.models else None


# ----------------------------------------------------------------------------- distributions
def pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def nb_pmf(n_max, mu, k):
    """Negative binomial pmf (mean mu, size k) for 0..n_max; Poisson when k is inf."""
    if not math.isfinite(k):
        return [pois(i, mu) for i in range(n_max + 1)]
    p = k / (k + mu)
    out = [p ** k]
    for i in range(1, n_max + 1):
        out.append(out[-1] * (i - 1 + k) / i * (1 - p))
    return out


def dc_tau(i, j, lh, la, rho):
    if i == 0 and j == 0:
        return 1 - lh * la * rho
    if i == 0 and j == 1:
        return 1 + lh * rho
    if i == 1 and j == 0:
        return 1 + la * rho
    if i == 1 and j == 1:
        return 1 - rho
    return 1.0


def score_dist(lh, la, rho=-0.06, n=11):
    """Full-time score distribution {(home, away): p} with Dixon-Coles low-score correction."""
    ph = [pois(i, lh) for i in range(n)]
    pa = [pois(j, la) for j in range(n)]
    d = {(i, j): max(0.0, ph[i] * pa[j] * dc_tau(i, j, lh, la, rho)) for i in range(n) for j in range(n)}
    s = sum(d.values())
    return {k: v / s for k, v in d.items()}


def half_dist(lh, la, tie=1.0, n=8):
    """Score distribution of one half: Poisson with a draw factor calibrated to the league's half draws."""
    base = {(i, j): pois(i, lh) * pois(j, la) for i in range(n) for j in range(n)}
    tm = sum(v for (i, j), v in base.items() if i == j)
    tie = min(tie, 0.95 / tm)
    return {(i, j): v * (tie if i == j else (1 - tm * tie) / (1 - tm)) for (i, j), v in base.items()}


def fit_rho(matches, model, grid=np.arange(-0.20, 0.081, 0.02)):
    """Dixon-Coles rho by likelihood over a league's matches given model rates (in-sample)."""
    pairs = []
    for m in matches:
        lh, la = model.expected_goals(m["home"], m["away"])
        pairs.append((m["home_goals"], m["away_goals"], lh, la))
    best = None
    for rho in grid:
        ll = 0.0
        for h, a, lh, la in pairs:
            if h <= 1 and a <= 1:
                ll += math.log(max(1e-9, dc_tau(h, a, lh, la, rho)))
            # normalisation: sum over the 4 corrected cells changes by -lh*la*rho + lh*rho + la*rho - rho *p11...
            z = (pois(0, lh) * pois(0, la) * (1 - lh * la * rho) + pois(0, lh) * pois(1, la) * (1 + lh * rho)
                 + pois(1, lh) * pois(0, la) * (1 + la * rho) + pois(1, lh) * pois(1, la) * (1 - rho))
            z0 = (pois(0, lh) * pois(0, la) + pois(0, lh) * pois(1, la) + pois(1, lh) * pois(0, la)
                  + pois(1, lh) * pois(1, la))
            ll -= math.log(1 + z - z0)
        if best is None or ll > best[0]:
            best = (ll, float(rho))
    return best[1]


def league_profile(matches):
    """Descriptive profile: goals, home share, draws, 1st-half share and half draws, stat means."""
    fin = [m for m in matches if m.get("home_goals") is not None]
    n = len(fin)
    if not n:
        return {}
    ht = [m for m in fin if m.get("ht") and m["ht"][0] is not None]
    g = sum(m["home_goals"] + m["away_goals"] for m in fin)
    g1 = sum(m["ht"][0] + m["ht"][1] for m in ht)
    gft_ht = sum(m["home_goals"] + m["away_goals"] for m in ht)
    prof = {
        "matches": n,
        "goals": g / n,
        "home_goals": sum(m["home_goals"] for m in fin) / n,
        "away_goals": sum(m["away_goals"] for m in fin) / n,
        "home_win": sum(m["home_goals"] > m["away_goals"] for m in fin) / n,
        "draw": sum(m["home_goals"] == m["away_goals"] for m in fin) / n,
        "over25": sum(m["home_goals"] + m["away_goals"] > 2.5 for m in fin) / n,
        "btts": sum(m["home_goals"] > 0 and m["away_goals"] > 0 for m in fin) / n,
        "h1_share": g1 / gft_ht if gft_ht else 0.45,
        "h1_draw": sum(m["ht"][0] == m["ht"][1] for m in ht) / len(ht) if ht else None,
        "h2_draw": sum((m["home_goals"] - m["ht"][0]) == (m["away_goals"] - m["ht"][1]) for m in ht) / len(ht)
        if ht else None,
    }
    for key in ("xg", "cor", "cards", "yc", "sh", "sot", "fo", "off"):
        vals = [stat_pair(m, key) for m in fin]
        vals = [v for v in vals if v]
        if len(vals) > 20:
            prof[key] = sum(a + b for a, b in vals) / len(vals)
    return prof


def half_tie_factor(prof, lh, la, half):
    """Draw factor that makes an average half match the league's half-time (or 2nd-half) draw rate."""
    rate = prof.get("h1_draw" if half == 1 else "h2_draw")
    if rate is None:
        return 1.0
    s = prof["h1_share"] if half == 1 else 1 - prof["h1_share"]
    tm = sum(pois(i, lh * s) * pois(i, la * s) for i in range(10))
    return rate / tm
