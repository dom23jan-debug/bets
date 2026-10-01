"""Walk-forward backtest to tune rating hyper-parameters per league.

For every week of the test season the ratings are refitted on all earlier matches and the next
week's games are predicted (60-min 1X2 from the calibrated score distribution). Metric: mean
log-loss (lower is better), compared with a no-skill baseline (league home/draw/away frequencies).
"""
import itertools
import math

from .model import Ratings, calibrate_shape, regulation, score_dist

GRID = {
    "half_life": (60, 120, 240),
    "offseason": (0.3, 0.6, 1.0),
    "shot_weight": (0.0, 0.3, 0.6, 0.9),
    "ridge": (3.0, 8.0),
}
WEEK = 7 * 86400
TOTAL_LINE = 5.5


def outcome(m):
    h, a = regulation(m)
    return 0 if h > a else (1 if h == a else 2)


def probs3(dist):
    p1 = sum(v for (i, j), v in dist.items() if i > j)
    px = sum(v for (i, j), v in dist.items() if i == j)
    return p1, px, max(1e-9, 1 - p1 - px)


def run(matches, regular, test_season="2025-2026", grid=GRID, total_grid=(0.0, 0.25, 0.5, 0.75, 1.0)):
    """Stage 1: strength hyper-parameters by 1X2 log-loss. Stage 2: total_k by O/U 5.5 log-loss."""
    shape, adj = calibrate_shape(regular)
    test = [m for m in regular if m.get("season") == test_season]
    if len(test) < 60:
        return None
    start, end = test[0]["start"] + WEEK, test[-1]["start"]   # include early season (cold start matters)
    cuts = list(range(start, end, WEEK))
    freq = [sum(outcome(m) == k for m in test) / len(test) for k in range(3)]
    over = sum(sum(regulation(m)) > TOTAL_LINE for m in test) / len(test)
    stage1 = _evaluate(matches, test, cuts, shape, adj, [dict(zip(grid.keys(), c), total_k=1.0)
                                                          for c in itertools.product(*grid.values())])
    stage1.sort(key=lambda x: x[2])
    best1 = stage1[0][1]
    stage2 = _evaluate(matches, test, cuts, shape, adj, [dict(best1, total_k=k) for k in total_grid])
    stage2.sort(key=lambda x: x[3])
    best = stage2[0]
    base = -sum(f * math.log(f) for f in freq)
    base_t = -(over * math.log(over) + (1 - over) * math.log(1 - over))
    return {"best": best, "baseline": base + base_t, "baseline_1x2": base, "baseline_total": base_t,
            "n": best[4], "shape": shape, "adj": adj, "stage1_top": stage1[:3], "stage2": stage2}


def _evaluate(matches, test, cuts, shape, adj, configs):
    # matches after the test season must not leak in
    matches = [m for m in matches if m["start"] <= test[-1]["start"]]
    results = []
    for params in configs:
        ll, llt, n = 0.0, 0.0, 0
        for cut in cuts:
            hist = [m for m in matches if m["start"] < cut]
            ahead = [m for m in test if cut <= m["start"] < cut + WEEK]
            if not ahead:
                continue
            r = Ratings(hist, now=cut, current=test[0]["season"], **params)
            for m in ahead:
                lh, la = r.expected_goals(m["home"], m["away"])
                d = score_dist(lh * adj, la * adj, shape)
                p = probs3(d)
                ll -= math.log(max(1e-9, p[outcome(m)]))
                po = sum(v for (i, j), v in d.items() if i + j > TOTAL_LINE)
                h, a = regulation(m)
                llt -= math.log(max(1e-9, po if h + a > TOTAL_LINE else 1 - po))
                n += 1
        results.append((ll / n + llt / n, params, ll / n, llt / n, n))
    return results
