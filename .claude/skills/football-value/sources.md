# Football data sources — status and API notes

## Status from the cloud container (tested 14 Oct 2026)
| Source | Status | Use |
|---|---|---|
| www.livesport.cz, local-cz.flashscore.ninja, global.ds.lsapp.eu | OK | backbone: fixtures, results, half-time, stats (xG, shots, corners, cards, fouls, offsides), odds of ~60 books via geo codes, opening odds, missing players / lineups |
| api.ifortuna.cz (+ www.ifortuna.cz) | OK | Fortuna offer API: all markets incl. corners, yellow cards, shots, SOT, fouls, offsides, team totals, player props |
| api.sofascore.com (+ www.sofascore.com) | OK | referee (career cards), missing players with reasons, lineups, bet365 odds incl. corners and cards lines (also historical, opening + closing), shotmap with xG |
| www.flashscore.com, isport.blesk.cz, raw.githubusercontent.com, github.com | OK | flashscore = same data as Livesport; GitHub raw = open datasets (StatsBomb open data, international results) |
| www.tipsport.cz, www.chance.cz, www.betano.cz, www.fotbal.cz | 403 (site blocks cloud IPs) | Czech odds come from Livesport instead |
| everything else tested (football-data.co.uk, understat, fbref, fotmob, transfermarkt, whoscored, pinnacle, betfair, smarkets, matchbook, kambi, oddsportal, betexplorer, the-odds-api, api-football, football-data.org, clubelo, eloratings, open-meteo, ESPN, UEFA, premierleague, FPL, forebet & co.) | blocked by the environment allowlist (curl 000 / proxy 403) | see "domains to add" |
FBref lost its Opta advanced data (xG etc.) in January 2026 — only basic stats left there.

## Livesport (football)
- League page `https://www.livesport.cz/fotbal/<country>/<league>/` → `country_id`, `tournament_id`, `seasonId`.
- Season results feed `https://local-cz.flashscore.ninja/1/x/feed/tr_1_<country>_<template>_<season>_<page>_2_cs_1`
  (header `x-fsign`), archive season id from `/fotbal/<country>/<league>-<2025-2026|2025>/vysledky/`.
- **List feeds carry the 2nd-half score in BC/BD** (no BA/BB) → half-time = full time − 2nd half.
- Stats `.../2/x/feed/df_st_1_<event>`: sections Match / 1st Half / 2nd Half; labels "Expected goals (xG)",
  "Total shots", "Shots on target", "Corner kicks", "Yellow cards" (row missing when 0), "Red cards", "Fouls",
  "Offsides", "Goalkeeper saves", "Big chances", "xG on target (xGOT)" ... xG exists for nearly all top
  divisions (not: German 3. Liga, Czech 2nd league, K League).
- Incidents `df_sui_1_<event>` (goals/cards with minutes, half scores), lineups `df_li_1_<event>`.
- Odds GraphQL `https://global.ds.lsapp.eu/odds/pq_graphql?_hash=oce&eventId=<id>&projectId=2&geoIpCode=<CC>&geoIpSubdivisionCode=<CC>01`
  → `value` (current / closing) and `opening`. Bookmakers by geo (Oct 2026): CZ Tipsport, Fortuna, Chance,
  Betano; SE Dbet, Coolbet, Unibet, Expekt, BetMGM, 1x2, MrGreen, bet365 (lowest margins ~2 %); KR Betssen,
  10x10bet, Momobet, Alphabet, 1xBet, Melbet (Asian-facing, ~2.5-4 %); GB 20 books incl. bet365, Betfair
  sportsbook, William Hill, Paddy Power; IT 13; FR 8; ES 9; DE 7; PL 6; AR/CL/IL... 1xBet, Betfair, Unibet,
  WH, bet365, bwin. No Pinnacle, no Betfair exchange. Markets: 1X2, DC, DNB, AH (incl. quarter lines), EH,
  O/U (Asian lines), BTTS, odd/even, correct score, HT/FT — full time, 1st half, 2nd half. No corners/cards.
- Persisted queries `https://global.ds.lsapp.eu/pq_graphql?_hash=<h>&eventId=<id>&projectId=2`:
  `dmpe2` missing players (+ participant ids, used instead of the 450 kB match page), `dplie` predicted
  lineups, `dlie2` lineups.
- EPL 1X2 closing margins 2025/26: Tipsport 2.8 %, Chance 2.8 %, Fortuna 4.0 %, Betano 6.0 %.

## Fortuna API (`https://api.ifortuna.cz/offer`, headers Origin/Referer www.ifortuna.cz)
- `/structure/api/v1_0/sports` (football = `ufo:sprt:00`), `/structure/api/v1_0/sport/ufo:sprt:00/tournaments?categories=true`
- `/structure/api/v1_0/tournament/<id>/matches` → fixtures with participants (HOME/AWAY ids) and start (ms)
- `/markets/api/v1_0/fixture/<id>/markets` → ~150 markets 3+ days before, ~700 on match day (statistics,
  player props, combos). Market names Czech, team markets carry `specifiers.teamId`.
- Results: `/result/api/v1_0/...` (sports, tournaments, fixtures).
- Rules: yellow-card markets ignore a second yellow, cards after the final whistle and to bench/staff.

## Sofascore API (`https://api.sofascore.com/api/v1`, browser User-Agent)
- `/unique-tournament/<ut>/seasons`, `/unique-tournament/<ut>/season/<sid>/events/{next|last}/<page>`
- `/event/<id>` (referee with career yellowCards/redCards/yellowRedCards/games; venue), `/event/<id>/lineups`
  (`confirmed`, `missingPlayers` with injury reason), `/event/<id>/statistics`, `/event/<id>/shotmap` (xG per
  shot), `/event/<id>/odds/1/all` (bet365: 1X2, DC, DNB, BTTS, goal lines, AH, **Cards in match**, **Corners
  2-Way**; `initialFractionalValue` = opening, `fractionalValue` = closing, `winning` flag),
  `/event/<id>/pregame-form`, `/event/<id>/h2h`, `/event/<id>/votes` (crowd), `/odds/providers/CZ/web`.
- `/sport/football/scheduled-tournaments/<date>/page/<n>`; `/sport/football/scheduled-events/<date>` is 404.
- Unique tournament ids: see `football/leagues.py` (`sofa`).

## Domains to add (Network access → Allowed domains; add bare domain AND `*.domain`)
Priority 1 (sharper reference prices, long backtests, xG history, cross-league ratings):
football-data.co.uk, pinnacle.com (guest.api.arcadia.pinnacle.com), betfair.com (ero.betfair.com),
understat.com, clubelo.com (api.clubelo.com — HTTP only? check), fotmob.com, transfermarkt.com,
fantasy.premierleague.com, eu-offering-api.kambicdn.com (Kambi/Unibet: corners, cards, shots markets).
Priority 2 (more books, odds history, news): oddsportal.com, betexplorer.com, oddschecker.com, oddspedia.com,
smarkets.com, matchbook.com, sazka.cz, synottip.cz, merkurxtip.cz, iforbet.cz, kingsbet.cz, fbref.com,
whoscored.com, footystats.org, soccerstats.com, totalcorner.com, adamchoi.co.uk, worldfootball.net,
soccerway.com, statz.ai, sportsgambler.com, premierinjuries.com, rotowire.com, bbc.co.uk/bbc.com, kicker.de,
uefa.com, premierleague.com (footballapi.pulselive.com), open-meteo.com, espn.com (site.api.espn.com),
americansocceranalysis.com, theanalyst.com.
Priority 3 (prediction sites, only as a second opinion): forebet.com, predictz.com, windrawwin.com,
vitibet.com, statarea.com, zulubet.com, soccervista.com, dratings.com, infogol.net, footballpredictions.com,
betclan.com, prosoccer.gr, olbg.com, bettingexpert.com.
API keys (optional, user must register): api-sports.io (API-Football), football-data.org, the-odds-api.com.
