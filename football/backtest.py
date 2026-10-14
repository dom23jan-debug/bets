"""Walk-forward backtest of the football models (weekly refits over a past season).

Goal model: 1X2 and over/under 2.5 log-loss vs. a no-skill baseline (league frequencies of the training data).
Statistics models: log-likelihood of match totals (corners, yellow cards, shots ...) under the model's
negative binomial vs. a league-mean negative binomial (positive gain = the team ratings add information).
"""
import itertools
import math

from .model import GoalModel, StatModels, nb_pmf, score_dist, stat_pair

WEEK = 7 * 86400


def outcome(m):
    h, a = m["home_goals"], m["away_goals"]
    return 0 if h > a else (1 if h == a else 2)


def probs3(d):
    p1 = sum(v for (i, j), v in d.items() if i > j)
    px = sum(v for (i, j), v in d.items() if i == j)
    return p1, px, max(1e-9, 1 - p1 - px)


def cuts_for(test):
    return list(range(test[0]["start"] + WEEK, test[-1]["start"] + 1, WEEK))


def goal_run(matches, test, configs, rho_default=-0.06):
    """[(1x2 + ou loss, params, ll_1x2, ll_ou, n)] for each parameter set."""
    cuts = cuts_for(test)
    results = []
    for prm in configs:
        ll, llt, n = 0.0, 0.0, 0
        for cut in cuts:
            hist = [m for m in matches if m["start"] < cut]
            ahead = [m for m in test if cut <= m["start"] < cut + WEEK]
            if not ahead or len(hist) < 100:
                continue
            gm = GoalModel(hist, cut, current=test[0]["season"], **prm)
            for m in ahead:
                lh, la = gm.expected_goals(m["home"], m["away"])
                d = score_dist(lh, la, rho_default)
                ll -= math.log(max(1e-9, probs3(d)[outcome(m)]))
                po = sum(v for (i, j), v in d.items() if i + j > 2.5)
                llt -= math.log(max(1e-9, po if m["home_goals"] + m["away_goals"] > 2.5 else 1 - po))
                n += 1
        if n:
            results.append((ll / n + llt / n, prm, ll / n, llt / n, n))
    return results


def baseline(train, test):
    freq = [max(1e-9, sum(outcome(m) == k for m in train) / len(train)) for k in range(3)]
    over = sum(m["home_goals"] + m["away_goals"] > 2.5 for m in train) / len(train)
    ll = -sum(math.log(freq[outcome(m)]) for m in test) / len(test)
    llt = -sum(math.log(over if m["home_goals"] + m["away_goals"] > 2.5 else 1 - over) for m in test) / len(test)
    return ll, llt


def stat_run(matches, test, prm, keys=("cor", "yc", "cards", "sh", "sot", "fo", "off"), ridge=None,
             half_life=None, per_team=False):
    """{stat: (model_ll, league_mean_ll, n)}: NB log-likelihood of match totals (or of each team's count
    with per_team) under the model vs. under the league mean (home / away means for teams)."""
    cuts = cuts_for(test)
    acc = {k: [0.0, 0.0, 0] for k in keys}
    p = dict(prm)
    if half_life:
        p["half_life"] = half_life
    for cut in cuts:
        hist = [m for m in matches if m["start"] < cut]
        ahead = [m for m in test if cut <= m["start"] < cut + WEEK]
        if not ahead or len(hist) < 100:
            continue
        gm = GoalModel(hist, cut, current=test[0]["season"], **p)
        sm = StatModels(hist, gm.weights, ridge=ridge or prm["ridge"], keys=keys)
        for k, r in sm.models.items():
            kk, kt = sm.k_total[k], sm.k_team[k]
            for m in ahead:
                y = stat_pair(m, k)
                if not y:
                    continue
                mh, ma = r.rates(m["home"], m["away"])
                a = acc[k]
                if per_team:
                    for obs, mu, base in ((y[0], mh, r.league_home), (y[1], ma, r.league_away)):
                        t = int(round(obs))
                        a[0] -= math.log(max(1e-12, nb_pmf(t, mu, kt)[t]))
                        a[1] -= math.log(max(1e-12, nb_pmf(t, base, kt)[t]))
                        a[2] += 1
                else:
                    t = int(round(y[0] + y[1]))
                    a[0] -= math.log(max(1e-12, nb_pmf(t, mh + ma, kk)[t]))
                    a[1] -= math.log(max(1e-12, nb_pmf(t, r.league_home + r.league_away, kk)[t]))
                    a[2] += 1
    return {k: (a[0] / a[2], a[1] / a[2], a[2]) for k, a in acc.items() if a[2]}


def grid_configs(grid):
    return [dict(zip(grid.keys(), c)) for c in itertools.product(*grid.values())]
