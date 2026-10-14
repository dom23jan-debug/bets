---
name: football-value
description: Value-bet analysis of football (soccer) matches against Czech bookmakers (Tipsport, Fortuna, Chance, Betano) - European leagues incl. second tiers, Champions/Europa/Conference League, MLS, Brazil, Argentina, Mexico, Japan, Korea, Australia, Saudi Arabia, China. Use whenever the user asks for fotbal / fotbalové value bety / tipy na fotbal, a football league, club or match, 1X2, double chance, draw no bet, Asian or European handicap, goals (počet gólů) incl. 1st/2nd half, BTTS, team goals, HT/FT, correct score, corners (rohy), cards (karty), shots (střely, na branku), fouls (fauly), offsides (ofsajdy) or any football statistics market.
---

# Football value betting — method and workflow

The user (Czech, answers in Czech) wants value bets: a price at a Czech bookmaker that is higher than the
fair price, with ¼-Kelly stakes (floor 0.5 %, cap 2 % of bankroll). Be honest: football markets are the most
efficient in betting - most matches are "bez value"; say "dnes nesázet" when nothing passes.

## What actually wins in football (read before trusting any number)
1. **The market is the best predictor.** Our goal model (Dixon-Coles on goals + xG) beats league base rates
   by 3-6 % log-loss, but the bookmaker consensus is clearly better (2025/26 closing 1X2: EPL model 1.031 vs
   consensus 1.013, LaLiga 1.007 vs 0.987). So the edge is **price discrepancy**: a Czech book offering more
   than the margin-free consensus of ~30-60 international books. The model is a sanity check, not the source.
2. **The consensus is calibrated**: in the 2025/26 backtest ROI followed EV vs consensus almost linearly
   (table below). Edges at odds above 3.2 were mostly stale long shots and lost → odds cap 3.2. Very large
   edges (EV > 1.06) still won at odds ≤ 3.2, but check the price still exists and no news explains the gap.
3. **The model is a filter**: value vs consensus where our model also sees value (EV_model ≥ 1) paid much
   better than where the model disagreed (+6.5 % vs +0.3 %, 7 leagues).
4. **Statistics markets (corners, cards) are priced by bookmakers about as well as by our count models.**
   Against bet365 lines (Sofascore) the corners model was ~break-even before margin and lost after it in most
   leagues; cards were mixed (definitions differ by bookmaker). Team-level counts (one team's corners/shots)
   are where the model adds information (+1.5-4.5 % log-likelihood vs league means), match totals barely
   (+0-1 %). Bet statistics only with a market reference (bet365 line) and small stakes.
5. Judge the method by **CLV** (our odds / closing odds) and ROI over hundreds of bets - never by one evening.

## Code (repo root, package `football/`)
- `livesport.py` — fixtures/results (half-time score derived: list feeds carry the 2nd-half score), match
  stats for the match and the 1st half (xG, shots, SOT, corners, yellow/red cards, fouls, offsides, saves,
  possession, big chances), odds incl. **opening odds** for any geo (`geoIpCode` CZ = Czech books; SE, KR, GB
  ... = international books), missing players. Cache `data/football/<league>.json.gz`.
- `leagues.py` — registry (Livesport path, Fortuna tournament name, Sofascore id, seasons, `model_filter`).
- `model.py` — ridge Poisson ratings on goals and xG (blend `xg_weight`), time decay `half_life`, summer break
  not ageing data, `offseason` discount, promoted-team prior, match total shrunk to league mean (`total_k`);
  Dixon-Coles rho per league; halves = league 1st-half share + half draw factor; count models (corners, cards,
  shots, SOT, fouls, offsides) with negative-binomial dispersion per league.
- `markets.py` — margin removal (power method), consensus (weights ∝ 1/(margin+1.5 %)², Czech books
  excluded), pricing of every market from score / count distributions, scan + ¼ Kelly (`kelly_stake`).
- `settle.py` — `python3 -m football.settle <event_id> ["market label"]`: final / half-time score, stats,
  closing odds of the Czech books (journal settlement + CLV); `--find "<home>" "<away>" <league>` → event id.
- `profiles.py` — markdown table of league profiles + tuning results (refresh `leagues.md`).
- `scan.py` — `python3 -m football.scan <league> <YYYY-MM-DD> [--all] [--no-extra]`: per match model λ,
  market-implied λ, consensus 1X2, model corners/cards/shots, referee, bet365 corner/card lines, candidates.
- `daily.py` — `python3 -m football.daily [date] [league ... | europe | all | cups]` → one ticket.
- `fortuna.py` — Fortuna offer API (statistics markets: corners, yellow cards, shots, SOT, fouls, offsides,
  team totals, "more X", team goals per half). `sofascore.py` — referee (career cards), missing players,
  lineups, bet365 odds incl. corners/cards lines (opening + closing, also historical).
- Maintenance: `tune.py` (walk-forward tuning → `data/football/params.json`), `odds_hist.py` (historical
  opening/closing odds), `market_bt.py` (backtest vs real Czech odds), `stat_bt.py` (corners/cards vs bet365).

## Procedure („najdi mi fotbalový value bet“)
1. Network check (one command, add football hosts):
   `for u in https://www.livesport.cz https://global.ds.lsapp.eu https://api.ifortuna.cz/offer/structure/api/v1_0/sports https://api.sofascore.com/api/v1/sport/football/categories; do echo "$u $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -A Mozilla/5.0 $u)"; done`
   `000` = blocked by the environment → tell the user the exact domain lines (bare + `*.domain`).
2. Settle open football bets in `journal/bets.csv` (results from Livesport, closing odds from
   `livesport.odds_rows(event_id)` after the match) — same rules as hockey (see CLAUDE.md).
3. Scan: `python3 -m football.daily [YYYY-MM-DD]` (all European leagues + UEFA cups with games that day,
   ~1-2 min per league with games). Other regions on request: `... daily <date> usa1 bra1 arg1 mex1 jpn1 kor1
   aus1 ksa1 chn1` (Americas run at night CET - scan after ~17:00 when lineups get closer).
4. Verify every candidate before recommending (checklist below). One bet per match. "AP" candidates
   (second tiers / untested leagues, > 3 h to kick-off) are not bets yet: tell the user the match and the
   „value od“ price and re-run `football.scan <league> <date>` ~2 h before kick-off (they turn into A if the
   gap survives). Prices move most after team news (~1 h before kick-off).
5. Answer in Czech: ticket table — čas, zápas, sázka, kurz + kancelář, úroveň (A/B/C), EV vs trh, EV model,
   „value od“ (minimum odds), vklad % (+ Kč when bankroll set) — plus one line „proč“ per bet (e.g. "Tipsport
   2.27 vs férových 2.18 z 31 zahraničních kanceláří, model 49 % vs trh 45 %"); then rejected candidates one
   line each. Remind: re-check the price before placing; value disappears when the price falls below „value od“.
6. Journal: append recommended bets to `journal/bets.csv` (league = football key, e.g. `eng1`, `cze1`, `ucl`),
   rejected ones to `journal/rejected.csv` with reason (same columns as hockey). No duplicates per date+match.
7. Commit & push data/journal/params to `main` (CLAUDE.md).

## Rules for candidates (implemented in `scan.tier`)
| Tier | Condition | Stake (¼ Kelly from EV vs trh) | Evidence |
|---|---|---|---|
| **A** | direct consensus (≥ 3 international books, same market + line), full-time 1X2 / DC / DNB / AH / totals / BTTS, EV trh ≥ 1.02, EV model ≥ 1.0, odds 1.5-3.2; outside `EARLY_OK` leagues only ≤ 3 h before kick-off | floor 0.5 %, cap 2 % | 2025/26 first divisions: +7.7 % at opening prices (1 138 bets), +21.6 % at closing (148) |
| **AP** | tier A edge in a second-tier / untested league more than 3 h before kick-off | not yet — re-scan ~2 h before kick-off | second tiers at opening prices −2.6 % (906 bets) |
| **A!** | tier A with EV trh > 1.06 | as A after checks | re-check the price, team news, lineups; gaps that big are often stale |
| **B** | direct consensus, other goal markets (1st / 2nd half, European handicap, HT/FT ...), EV trh ≥ 1.04, EV model ≥ 1.0, odds ≤ 3.2 | 0.5 % | weak evidence (half totals EV ≥ 1.04: +7 % on 132 bets, below that −2 %) |
| **C** | match totals of corners / yellow cards at Fortuna vs the bet365 line (Sofascore), EV trh ≥ 1.05, EV model ≥ 1.0, odds ≤ 3.2 | 0.5 % | experimental, no historical Fortuna prices → track in the journal |
| — | `trh*` (prices implied from the consensus λ: Fortuna team totals, lines not offered abroad) | never | lost in the backtest |
| **S** | `jen model` corners / cards markets (team corners, "more corners", team cards) with EV model ≥ 1.15 | never on the ticket — log to `rejected.csv` | no market reference |
| — | shots, shots on target, fouls, offsides | never | Fortuna counts more shots than Livesport/Opta: its main lines (26.5-29.5) sit ~10 % above Livesport league means (24.6-26.5) → model "unders" are artefacts. Model expectations are printed for information only |
- UEFA cups (`model_filter=False`): consensus only — our per-league ratings cannot compare teams across leagues.
- Prefer full-time main markets (1X2/AH/DNB/totals) over halves, HT/FT, correct score.
- Max odds 3.2 on the ticket (user's choice, same as hockey) unless the user asks for longer odds.
- A model-vs-consensus gap never creates value by itself (the model is behind the market: promoted teams,
  transfers, injuries). Value = consensus EV; the model only has to agree (EV_model ≥ 1).
- Same match, several tier-A offers: take the best one (daily.py does), never stack correlated bets.
- Early season (< 5 league games per team) paid best in the backtest (+9 % vs +1 % late) - no stake cut.

## Verification checklist (football specific)
- **Team news**: `sofascore.lineups(event_id)` / `livesport.missing_players(id)` (injuries, suspensions);
  confirmed lineups ~60 min before kick-off. Missing key striker/keeper/2+ defenders → price moves.
- **Rotation**: European midweek before/after, cup ties, after the international break, dead rubbers late in
  the season, title already decided; big clubs rotate in domestic cups.
- **Motivation / context**: relegation fights, derbies (more cards), new coach bounce, travel (UECL away trips).
- **Referee** (cards): scan prints the appointed referee's career yellow cards per game and the multiplier.
- **Weather**: heavy rain / strong wind → fewer goals (only extreme cases matter).
- **Rules differ by bookmaker**: Fortuna yellow-card markets do not count a second yellow, cards after the
  final whistle or to bench/staff; corners exclude extra time. Always 90 min + stoppage time.
- Check the price at the Czech book right before betting; football lines move fast after team news.

## Backtest results (season 2025/26, walk-forward weekly refits, real Czech prices from Livesport)
Run 14 Oct 2026 on 14 leagues (eng1, eng2, esp1, esp2, ita1, ita2, ger1, ger2, fra1, fra2, ned1, por1,
bel1, cze1; `odds_hist` → `market_bt` → `bt_report`). Consensus = SE + KR + GB books, Czech books excluded.
- **Calibration** (all Czech offers, closing prices, odds ≤ 3.2, 7 leagues): ROI by EV vs consensus
  0.98-1.00 −1.0 %, 1.00-1.01 +0.2 %, 1.01-1.02 +0.9 %, 1.02-1.03 +4.0 %, 1.03-1.05 +10.8 %,
  1.05-1.08 +23 % (57 bets). Above odds 3.2 the big "edges" lost (stale long shots) → odds cap 3.2.
- **Final rule = tier A, one bet per match** (16 leagues: + eng3, eng4):
  | prices | league group | bets | ROI flat | note |
  |---|---|---|---|---|
  | opening (bet early) | first divisions (eng1 esp1 ita1 ger1 fra1 ned1 por1 bel1 cze1) | 1 138 | **+7.7 % ± 3.1** | `leagues.EARLY_OK` |
  | opening | second tiers (eng2-4, esp2, ita2, ger2, fra2) | 906 | −2.6 % ± 3.4 | early value not real |
  | closing (bet late) | first divisions | 148 | +21.6 % ± 9.5 | |
  | closing | second tiers | 34 | +31.4 % ± 20 | consensus reliable near kick-off |
  → tier A anytime in `EARLY_OK` leagues; elsewhere only within 3 h of kick-off ("AP" = re-scan later).
  Opening prices by league: bel1 +26 %, eng1 +16 %, ned1 +10 %, ita1 +8 %, eng2 +7 %, cze1 +4 %, fra1 +4 %,
  esp1 +2 %, por1 +2 %, ger1 +1 %, fra2 −1 %, ger2 −1 %, eng3 −3 %, eng4 −4 %, ita2 −4 %, **esp2 −15 %**.
- The model filter matters: in the EV 1.015-1.06 band offers where the model agreed returned +6.5 % vs
  +0.3 % where it did not (7 leagues, closing prices).
- **cze1** is the richest source of discrepancies (closing: 202 offers with EV ≥ 1.03 → +16 %, vs 30 in eng1).
- Bookmakers (EV 1.015-1.06, 7 leagues): Fortuna +16 %, Betano +2.7 %, Tipsport +1.5 %, Chance −0.2 %.
- Implied-only prices (trh*, team totals from the consensus λ) lost → never a tier. Half-time totals with a
  direct consensus: EV 1.02-1.04 −2 %, EV ≥ 1.04 +7 % (open, 132 bets) → tier B, minimum stake only.
- Corners / cards models vs bet365 lines (`stat_bt`): log-loss model ≈ bet365 (0.684-0.703 vs 0.685-0.693);
  betting the model at bet365 opening prices: corners −11 % … +15 % by league (≈ 0 overall), cards −17 %
  (LaLiga, counting differs) … +8 % (Championship) → tier C only vs the bet365 line, experimental.
- Caveats: one season; model-filter hyper-parameters tuned on the same season (mild optimism); Czech
  books limit accounts that win steadily - spread bets over books, keep stakes modest, track CLV.

## Data sources
See `sources.md` (status of every domain tested from the cloud container, API endpoints, what to add).
