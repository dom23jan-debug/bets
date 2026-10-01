"""League registry. Hyper-parameters come from `python3 -m hockey.tune <league>` (walk-forward backtest)
and are stored in data/params.json; the defaults below are used until a league is tuned."""
import json
import os

from .livesport import CACHE

LEAGUES = {
    "shl": {"name": "SHL (Švédsko)", "path": "svedsko/shl", "w_model": 0.4},
    "del": {"name": "DEL (Německo)", "path": "nemecko/del", "w_model": 0.4},
    "nl": {"name": "National League (Švýcarsko)", "path": "svycarsko/national-league", "w_model": 0.4},
    "elh": {"name": "Tipsport extraliga (Česko)", "path": "cesko/extraliga", "w_model": 0.4},
    "sk": {"name": "Tipsport liga (Slovensko)", "path": "slovensko/extraliga", "w_model": 0.5},
    "fr": {"name": "Ligue Magnus (Francie)", "path": "francie/ligue-magnus", "w_model": 0.5},
    "liiga": {"name": "Liiga (Finsko)", "path": "finsko/liiga", "w_model": 0.4},
    "maxa": {"name": "Maxa liga (Česko 2)", "path": "cesko/maxa-liga", "w_model": 0.5},
}
# stages that are not regular-season league play (playoffs, relegation, qualification)
NON_REGULAR = ("Play Off", "Play Out", "udržení", "Předkolo", "Baráž", "Kvalifikace", "Play In", "Relegation")
DEFAULT_PARAMS = {"half_life": 45, "offseason": 0.6, "shot_weight": 0.6, "ridge": 0.5}
PARAMS_FILE = os.path.join(CACHE, "params.json")


def params(key):
    stored = json.load(open(PARAMS_FILE)) if os.path.exists(PARAMS_FILE) else {}
    return stored.get(key, {}).get("params", DEFAULT_PARAMS)


def save_params(key, entry):
    stored = json.load(open(PARAMS_FILE)) if os.path.exists(PARAMS_FILE) else {}
    stored[key] = entry
    json.dump(stored, open(PARAMS_FILE, "w"), indent=1, ensure_ascii=False)


def is_regular(m):
    return not any(s in (m.get("stage") or "") for s in NON_REGULAR)
