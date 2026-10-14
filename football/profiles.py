"""Markdown table of league profiles (last two seasons of league play) + tuning results, for the skill's
leagues.md.

Usage: python3 -m football.profiles [league ...] > .claude/skills/football-value/leagues_table.md
"""
import json
import os
import sys

from .leagues import LEAGUES, PARAMS_FILE, is_regular
from .livesport import cache_path, load_cache
from .model import league_profile


def main():
    keys = [a for a in sys.argv[1:] if a in LEAGUES] or list(LEAGUES)
    tuned = json.load(open(PARAMS_FILE)) if os.path.exists(PARAMS_FILE) else {}
    print("| liga | zápasů | góly | 1. pol. | domácí | remíza | >2.5 | BTTS | rohy | ŽK | střely | fauly | "
          "1X2 vs base | xG váha |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k in keys:
        if not os.path.exists(cache_path(k)):
            continue
        c = load_cache(k)
        ms = [dict(m, **c["stats"].get(i, {})) for i, m in c["matches"].items()
              if m.get("home_goals") is not None and is_regular(m) and m.get("season") in LEAGUES[k]["seasons"]]
        if len(ms) < 50:
            continue
        p = league_profile(ms)
        t = tuned.get(k, {})
        gain = f"{t['gain_1x2_pct']:+.1f} %" if "gain_1x2_pct" in t else "–"
        xw = t.get("params", {}).get("xg_weight", "–")

        def f(key, fmt="{:.1f}"):
            return fmt.format(p[key]) if key in p else "–"

        print(f"| {k} {LEAGUES[k]['name']} | {p['matches']} | {p['goals']:.2f} | {100 * p['h1_share']:.0f} % | "
              f"{100 * p['home_win']:.0f} % | {100 * p['draw']:.0f} % | {100 * p['over25']:.0f} % | "
              f"{100 * p['btts']:.0f} % | {f('cor')} | {f('yc')} | {f('sh')} | {f('fo')} | {gain} | {xw} |")


if __name__ == "__main__":
    main()
