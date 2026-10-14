"""Tune the goal-model hyper-parameters of a league by walk-forward backtest over season 2025/26 and check
the statistics models (corners, cards, shots ...) against a league-mean baseline.

Usage: python3 -m football.tune eng1 [esp1 ...] [--quick]
Result -> data/football/params.json (params + log-loss vs. baseline + stats-model gains).
"""
import sys
import time

from .backtest import baseline, goal_run, grid_configs, stat_run
from .leagues import LEAGUES, is_regular, save_params
from .livesport import load_league

GRID = {"half_life": (180, 365), "offseason": (0.6, 0.9), "xg_weight": (0.4, 0.7, 0.9), "ridge": (2.0,),
        "total_k": (0.25, 0.75)}
QUICK = {"half_life": (365,), "offseason": (0.7,), "xg_weight": (0.6, 0.9), "ridge": (2.0,), "total_k": (0.5,)}


def test_season(cfg):
    return cfg["seasons"][0]


def tune(key, grid=GRID):
    cfg = LEAGUES[key]
    t0 = time.time()
    _, matches = load_league(key, cfg["path"], cfg["seasons"], refresh_current=False)
    matches = [m for m in matches if m.get("home_goals") is not None]
    season = test_season(cfg)
    test = [m for m in matches if m.get("season") == season and is_regular(m)]
    if len(test) < 100:
        print(key, "not enough data")
        return None
    hist = [m for m in matches if m["start"] <= test[-1]["start"]]
    res = sorted(goal_run(hist, test, grid_configs(grid)), key=lambda r: r[0])
    loss, best, ll, llt, n = res[0]
    train = [m for m in hist if m["start"] < test[0]["start"]]
    b1, bt = baseline(train, test)
    st = stat_run(hist, test, best, ridge=8.0)
    entry = {"params": best, "test_season": season, "n_test": n,
             "logloss_1x2": round(ll, 4), "baseline_1x2": round(b1, 4),
             "logloss_ou25": round(llt, 4), "baseline_ou25": round(bt, 4),
             "gain_1x2_pct": round(100 * (b1 - ll) / b1, 2), "gain_ou25_pct": round(100 * (bt - llt) / bt, 2),
             "stats_gain_pct": {k: round(100 * (b - m) / b, 2) for k, (m, b, _) in st.items()},
             "top3": [r[1] for r in res[:3]]}
    save_params(key, entry)
    print(f"{key}: 1X2 {ll:.4f} vs {b1:.4f} ({entry['gain_1x2_pct']:+.2f} %) | O/U2.5 {llt:.4f} vs {bt:.4f} "
          f"({entry['gain_ou25_pct']:+.2f} %) | {best} | stats {entry['stats_gain_pct']} | {time.time() - t0:.0f}s",
          flush=True)
    return entry


if __name__ == "__main__":
    g = QUICK if "--quick" in sys.argv else GRID
    for k in [a for a in sys.argv[1:] if not a.startswith("--")]:
        tune(k, g)
