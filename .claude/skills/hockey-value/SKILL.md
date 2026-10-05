---
name: hockey-value
description: Value-bet analysis of ice-hockey matches (any league) against Czech bookmakers (Tipsport, Fortuna, Chance, Betano). Use whenever the user asks to analyse hockey matches/a hockey league for value bets, EV, Kelly stakes, odds comparison, totals, handicaps or period markets. Per-league specifics live in the hockey-<league> skills.
---

# Hockey value betting — common workflow

The user (Czech, answers in Czech) wants: implied probabilities → own probabilities → EV → value bets
with ¼-Kelly stakes (0.5–3 % bankroll). Be honest: if nothing has value, say "nesázet".

## Code (repo root)
- `hockey/livesport.py` — Livesport data: fixtures, results with period scores, match stats (shots,
  saves, penalties), odds of Czech bookmakers for every market. JSON cache in `data/<league>.json`.
- `hockey/model.py` — ratings = ridge Poisson regression on regulation goals and on shots on goal
  (shots → goals via league shooting %), exponential time decay, offseason discount; match total
  shrunk toward league mean (`total_k`); score distribution = Poisson + tie inflation + late
  goalie-pull phase (EN goals, late equalisers) calibrated per league; 1st-period distribution.
- `hockey/backtest.py`, `hockey/tune.py` — walk-forward backtest (weekly refits over season
  2025/26). Stage 1 tunes strength params on 1X2 log-loss, stage 2 tunes `total_k` on O/U 5.5
  log-loss. Results in `data/params.json` (with log-loss vs. no-skill baseline).
- `hockey/markets.py` — prices every market from the score distribution (1X2, DC, DNB, handicaps incl.
  quarter lines, totals 60 min and incl. OT, BTTS, odd/even, 1st period), removes bookmaker margin,
  blends EV: `EV = w_model·EV_model + (1−w_model)·EV_market` at the best available odds.
- `hockey/scan.py` — `python3 -m hockey.scan <league> <YYYY-MM-DD> [--all]`.
- `hockey/leagues.py` — league registry (Livesport path, `w_model`).
- Older single-league scripts: `liiga_value.py` (liiga.fi xG), `maxa_markets.py`, `nhl_value.py`.

## Procedure
1. Check network first: `curl -s -o /dev/null -w '%{http_code}' https://www.livesport.cz` (+ league
   specific hosts from its skill). If a host is blocked, tell the user immediately with the exact
   domain line to add (they add domains in the environment's Network access, Custom list).
2. `pip install -q numpy scipy` if missing.
3. If the league was never tuned or a month passed: `python3 -m hockey.tune <league>` (~3 min).
4. `python3 -m hockey.scan <league> <date>` → candidates with EV ≥ 1.03.
5. Sanity-check every candidate before recommending:
   - big model–market gaps (> 8–10 pp) usually mean missing info (injuries, goalie, roster, B-team) →
     look for news / starting goalie; prefer to skip rather than trust the model;
   - one bet per match (bets in the same match are correlated); prefer lower-variance versions
     (e.g. +1.5 handicap instead of outright) when EV is similar;
   - early season (< 10 games per team) → halve stakes;
   - quote the "value od" price: the user must re-check odds before placing.
6. Output in Czech: table per match (market vs model), recommended bets with odds, bookmaker, EV,
   stake (¼ Kelly, cap 3 %, floor 0.5 % — below that say "vynechat"), plus a clear verdict.
7. Commit code/param changes and push to the working branch.

## Data source status (checked 1 Oct 2026 from the cloud container)
| Source | Status | Use |
|---|---|---|
| livesport.cz + flashscore.ninja + lsapp.eu | OK | results, periods, SOG, odds — backbone for all leagues |
| liiga.fi | OK (domain must be allowed) | Liiga xG per game |
| shl.se, stats.swehockey.se | OK | SHL play-by-play with shot coordinates → own xG |
| penny-del.org, nationalleague.ch, data.sihf.ch, hockeyfrance.com, hockeytech.com | reachable | not integrated yet (next step: lineups/goalies) |
| eliteprospects.com, hockeyslovakia.sk, hokej.cz, tipsport.cz, chance.cz | 403 (site blocks cloud/foreign IPs) | unusable |
| tiposextraliga.sk | does not resolve | league renamed (Tipsport liga) |

## Interpretation rules learned so far
- Backtest vs. real closing odds 2025/26 (`hockey.market_bt`, 8 leagues, 2 888 games, checked 5 Oct 2026):
  market 1X2 log-loss 1.0038 vs model 1.0119 (optimal blend w ≈ 0.1). Current rule (EV ≥ 1.03, best per
  match) ≈ +1 % ROI over 1 534 bets, but **all of it early season**: teams ≤ 10 games +15 % (381 bets,
  6 of 8 leagues positive), later −5 to −8 % whatever w/EV threshold → `hockey.daily` keeps those
  off the ticket (`EARLY_GAMES`). Odds-only outliers (best odds ≥ 1.03 × fair, no model) lost −15 %;
  totals −4 %; "safe" favourites at odds 1.3–2.0 ≈ break-even before nothing (−4 to +2 %).
- Hockey 1X2 is noisy: a good model beats league base rates by only ~0.5 % log-loss; the market is
  usually better → keep w_model ≤ 0.5 and treat large disagreements with suspicion.
- Team-specific totals are mostly noise; the league mean is a strong prior (`total_k`).
- Empty-net goals make 2–3 goal margins common → never price handicaps/totals with plain Poisson.
- Cold start: the summer break must not age last season's data (handled via "hockey days"), and
  promoted teams start below average — otherwise October ratings rest on 3–4 games (bug fixed 1 Oct 2026).
- Track every bet (stake, odds, closing odds, result) — judge by CLV and ROI over hundreds of bets,
  not one evening.
