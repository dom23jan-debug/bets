"""Football league registry. Hyper-parameters come from `python3 -m football.tune <league>` (walk-forward
backtest) and are stored in data/football/params.json; DEFAULT_PARAMS are used until a league is tuned.

Value comes from the bookmaker consensus; the own model is a filter (it must agree). UEFA cups mix teams
from different leagues that our per-league ratings cannot compare -> model_filter=False (consensus only).
"""
import json
import os

from .livesport import CACHE

EU2 = ("2025-2026", "2024-2025")      # autumn-spring leagues: two archive seasons + current
YR2 = ("2025", "2024")                # calendar-year leagues


def L(name, path, fortuna, sofa, seasons=EU2, **kw):
    """name, Livesport path, Fortuna tournament name, Sofascore unique-tournament id, archive seasons."""
    return dict(name=name, path=path, fortuna=fortuna, sofa=sofa, seasons=seasons, **kw)


LEAGUES = {
    # --- top 5 + second tiers
    "eng1": L("Premier League (Anglie)", "anglie/premier-league", "1. Anglie", 17),
    "eng2": L("Championship (Anglie 2)", "anglie/championship", "2. Anglie", 18),
    "eng3": L("League One (Anglie 3)", "anglie/league-one", "3. Anglie", 24),
    "eng4": L("League Two (Anglie 4)", "anglie/league-two", "4. Anglie", 25),
    "esp1": L("LaLiga (Španělsko)", "spanelsko/laliga", "1. Španělsko", 8),
    "esp2": L("LaLiga2 (Španělsko 2)", "spanelsko/laliga2", "2. Španělsko", 54),
    "ita1": L("Serie A (Itálie)", "italie/serie-a", "1. Itálie", 23),
    "ita2": L("Serie B (Itálie 2)", "italie/serie-b", "2. Itálie", 53),
    "ger1": L("Bundesliga (Německo)", "nemecko/bundesliga", "1. Německo", 35),
    "ger2": L("2. Bundesliga (Německo 2)", "nemecko/2-bundesliga", "2. Německo", 44),
    "ger3": L("3. Liga (Německo 3)", "nemecko/3-liga", "3. Německo", 491),
    "fra1": L("Ligue 1 (Francie)", "francie/ligue-1", "1. Francie", 34),
    "fra2": L("Ligue 2 (Francie 2)", "francie/ligue-2", "2. Francie", 182),
    # --- other European leagues
    "ned1": L("Eredivisie (Nizozemsko)", "nizozemsko/eredivisie", "1. Nizozemsko", 37),
    "ned2": L("Eerste Divisie (Nizozemsko 2)", "nizozemsko/eerste-divisie", "2. Nizozemsko", 131),
    "por1": L("Liga Portugal (Portugalsko)", "portugalsko/liga-portugal", "1. Portugalsko", 238),
    "bel1": L("Jupiler Pro League (Belgie)", "belgie/jupiler-pro-league", "1. Belgie", 38),
    "tur1": L("Süper Lig (Turecko)", "turecko/superliga", "1. Turecko", 52),
    "sco1": L("Premiership (Skotsko)", "skotsko/premiership", "1. Skotsko", 36),
    "aut1": L("Bundesliga (Rakousko)", "rakousko/bundesliga", "1. Rakousko", 45),
    "sui1": L("Super League (Švýcarsko)", "svycarsko/super-league", "1. Švýcarsko", 215),
    "den1": L("Superliga (Dánsko)", "dansko/superliga", "1. Dánsko", 39),
    "cze1": L("Chance Liga (Česko)", "cesko/chance-liga", "1. Česko", 172),
    "cze2": L("Chance Národní liga (Česko 2)", "cesko/chance-narodni-liga", "2. Česko", None),
    "svk1": L("Niké liga (Slovensko)", "slovensko/nike-liga", "1. Slovensko", 211),
    "pol1": L("Ekstraklasa (Polsko)", "polsko/ekstraklasa", "1. Polsko", 202),
    "gre1": L("Super League (Řecko)", "recko/super-league", "1. Řecko", 185),
    "cro1": L("HNL (Chorvatsko)", "chorvatsko/hnl", "1. Chorvatsko", 170),
    "srb1": L("Super liga (Srbsko)", "srbsko/super-liga", "1. Srbsko", 210),
    "rou1": L("Superliga (Rumunsko)", "rumunsko/superliga", "1. Rumunsko", 152),
    "hun1": L("NB I (Maďarsko)", "madarsko/nb-i", "1. Maďarsko", 187),
    "nor1": L("Eliteserien (Norsko)", "norsko/eliteserien", "1. Norsko", 20, seasons=YR2),
    "swe1": L("Allsvenskan (Švédsko)", "svedsko/allsvenskan", "1. Švédsko", 40, seasons=YR2),
    "fin1": L("Veikkausliiga (Finsko)", "finsko/veikkausliiga", "1. Finsko", 41, seasons=YR2),
    # --- Americas / Asia
    "usa1": L("MLS (USA)", "usa/mls", "USA - MLS", 242, seasons=YR2),
    "mex1": L("Liga MX (Mexiko)", "mexiko/liga-mx", "1. Mexiko", 11621),
    "bra1": L("Série A (Brazílie)", "brazilie/serie-a", "1. Brazílie", 325, seasons=YR2),
    "arg1": L("Liga Profesional (Argentina)", "argentina/liga-profesional", "1. Argentina", 155, seasons=YR2),
    "jpn1": L("J1 League (Japonsko)", "japonsko/j1-league", "1. Japonsko", 196, seasons=("2026", "2025")),
    "kor1": L("K League 1 (Jižní Korea)", "jizni-korea/k-league-1", "1. J.Korea", 410, seasons=YR2),
    "aus1": L("A-League (Austrálie)", "australie/a-league", "1. Austrálie", 136),
    "ksa1": L("Saudi Pro League (Saúdská Arábie)", "saudska-arabie/saudi-professional-league", "1. Saudská Arábie", 955),
    "chn1": L("Super League (Čína)", "cina/superliga", "1. Čína", 649, seasons=YR2),
    # --- UEFA club competitions: teams from different leagues -> consensus only (no model filter)
    "ucl": L("Liga mistrů", "evropa/liga-mistru", "Liga mistrů", 7, model_filter=False),
    "uel": L("Evropská liga", "evropa/evropska-liga", "Evropská liga", 679, model_filter=False),
    "uecl": L("Konferenční liga", "evropa/konferencni-liga", "Konferenční liga", 17015, model_filter=False),
}
# European first divisions: tier A held at opening prices too (backtest 2025/26, one bet per match: the 9 leagues
# used to set the rule +7.7 % on 1 138 bets, 8 further first divisions out-of-sample +8.1 % on 597 bets; second
# tiers -2.6 % on 906 bets). Elsewhere (second tiers, non-European leagues, UEFA cups - untested) a tier-A edge
# counts only close to kick-off (scan.LATE_HOURS), when the international consensus has formed.
EARLY_OK = {"eng1", "esp1", "ita1", "ger1", "fra1", "ned1", "por1", "bel1", "cze1",       # set the rule
            "tur1", "den1", "pol1", "sco1", "svk1", "aut1", "sui1", "gre1",              # out-of-sample
            "cro1", "srb1", "rou1", "hun1", "nor1", "swe1", "fin1"}                      # first divisions, untested
# Default scan set ("all European leagues"); the rest is scanned when asked for by name / region.
EUROPE = [k for k in LEAGUES if k not in ("usa1", "mex1", "bra1", "arg1", "jpn1", "kor1", "aus1", "ksa1", "chn1")]
CUPS = ("ucl", "uel", "uecl")
# stages that are not regular league play
NON_REGULAR = ("Play Off", "Play-off", "Play Out", "Baráž", "Kvalifikace", "Předkolo", "Relegation", "Postup",
               "Sestup", "o udržení", "Finále", "Semifinále", "Čtvrtfinále")
DEFAULT_PARAMS = {"half_life": 365, "offseason": 0.7, "xg_weight": 0.7, "ridge": 2.0, "total_k": 0.5}
PARAMS_FILE = os.path.join(CACHE, "params.json")


def params(key):
    stored = json.load(open(PARAMS_FILE)) if os.path.exists(PARAMS_FILE) else {}
    return dict(DEFAULT_PARAMS, **stored.get(key, {}).get("params", {}))


def save_params(key, entry):
    stored = json.load(open(PARAMS_FILE)) if os.path.exists(PARAMS_FILE) else {}
    stored[key] = entry
    os.makedirs(os.path.dirname(PARAMS_FILE), exist_ok=True)
    json.dump(stored, open(PARAMS_FILE, "w"), indent=1, ensure_ascii=False)


def is_regular(m):
    return not any(s in (m.get("stage") or "") for s in NON_REGULAR)
