"""Tune rating hyper-parameters of a league by walk-forward backtest.

Usage: python3 -m hockey.tune shl [del nl ...]
"""
import sys

from .backtest import run
from .leagues import LEAGUES, is_regular, save_params
from .livesport import load_league

GRID = {"half_life": (30, 60, 120), "offseason": (0.4, 0.7, 1.0), "shot_weight": (0.3, 0.6, 0.8),
        "ridge": (0.5, 1.5, 4.0)}


def tune(key):
    _, matches = load_league(key, LEAGUES[key]["path"], seasons=("2025-2026", "2024-2025"))
    regular = [m for m in matches if is_regular(m)]
    r = run(matches, regular, grid=GRID)
    if not r:
        print(key, "not enough data")
        return
    ll, best, ll_1x2, ll_tot, _ = r["best"]
    gain = (r["baseline"] - ll) / r["baseline"]
    save_params(key, {"params": best, "logloss": round(ll, 4), "baseline": round(r["baseline"], 4),
                      "logloss_1x2": round(ll_1x2, 4), "baseline_1x2": round(r["baseline_1x2"], 4),
                      "logloss_total": round(ll_tot, 4), "baseline_total": round(r["baseline_total"], 4),
                      "gain_pct": round(100 * gain, 2), "n_test": r["n"]})
    print(f"{key}: log-loss {ll:.4f} vs baseline {r['baseline']:.4f} ({100*gain:+.2f} %) | 1X2 {ll_1x2:.4f} "
          f"vs {r['baseline_1x2']:.4f} | O/U5.5 {ll_tot:.4f} vs {r['baseline_total']:.4f} | {best}")


if __name__ == "__main__":
    for k in sys.argv[1:]:
        tune(k)
