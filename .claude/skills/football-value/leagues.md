# Football leagues — keys, profiles, notes

Keys are used in the journal (`league` column) and on the command line (`football.scan <key> <date>`).
Profile = league matches of the last two completed seasons (Livesport data); "1X2 vs base" = log-loss gain of
the tuned goal model over league base rates in the 2025/26 walk-forward test; "xG váha" = tuned xg_weight.
Refresh: `python3 -m football.profiles > /tmp/t.md` and paste below.

| liga | zápasů | góly | 1. pol. | domácí | remíza | >2.5 | BTTS | rohy | ŽK | střely | fauly | 1X2 vs base | xG váha |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eng1 Premier League (Anglie) | 760 | 2.84 | 45 % | 42 % | 26 % | 56 % | 57 % | 10.1 | 4.0 | 25.5 | 21.9 | +5.4 % | 0.7 |
| eng2 Championship (Anglie 2) | 1104 | 2.53 | 46 % | 44 % | 27 % | 48 % | 54 % | 10.2 | 3.8 | 24.6 | 22.3 | +2.8 % | 0.7 |
| eng3 League One (Anglie 3) | 1104 | 2.61 | 44 % | 45 % | 25 % | 51 % | 52 % | 9.9 | 3.8 | 23.3 | 23.2 | +2.5 % | 0.9 |
| eng4 League Two (Anglie 4) | 1104 | 2.54 | 44 % | 42 % | 27 % | 47 % | 51 % | 9.7 | 4.0 | 23.8 | 23.4 | +4.6 % | 0.9 |
| esp1 LaLiga (Španělsko) | 760 | 2.66 | 43 % | 47 % | 25 % | 49 % | 55 % | 9.6 | 4.5 | 24.4 | 25.0 | +6.8 % | 0.7 |
| esp2 LaLiga2 (Španělsko 2) | 924 | 2.58 | 43 % | 46 % | 27 % | 49 % | 54 % | 9.4 | 5.0 | 24.9 | 26.8 | +1.6 % | 0.7 |
| ita1 Serie A (Itálie) | 760 | 2.49 | 43 % | 39 % | 27 % | 47 % | 48 % | 9.1 | 3.8 | 24.4 | 25.2 | +8.5 % | 0.4 |
| ita2 Serie B (Itálie 2) | 764 | 2.51 | 46 % | 43 % | 32 % | 47 % | 54 % | 9.3 | 4.7 | 25.9 | 29.8 | +3.2 % | 0.9 |
| ger1 Bundesliga (Německo) | 612 | 3.18 | 46 % | 41 % | 25 % | 62 % | 59 % | 9.7 | 3.8 | 26.2 | 21.1 | +9.6 % | 0.7 |
| ger2 2. Bundesliga (Německo 2) | 612 | 2.98 | 45 % | 43 % | 26 % | 59 % | 60 % | 10.2 | 4.7 | 26.9 | 24.1 | +3.2 % | 0.9 |
| ger3 3. Liga (Německo 3) | 760 | 3.06 | 44 % | 46 % | 24 % | 60 % | 62 % | 10.3 | 5.0 | 19.8 | 25.1 | +4.5 % | 0.4 |
| fra1 Ligue 1 (Francie) | 612 | 2.90 | 44 % | 46 % | 22 % | 54 % | 54 % | 9.5 | 3.8 | 24.8 | 24.1 | +6.8 % | 0.9 |
| fra2 Ligue 2 (Francie 2) | 612 | 2.56 | 45 % | 43 % | 27 % | 48 % | 50 % | 9.4 | 3.9 | 23.3 | 27.1 | +4.2 % | 0.7 |
| ned1 Eredivisie (Nizozemsko) | 612 | 3.08 | 45 % | 45 % | 26 % | 58 % | 59 % | 10.2 | 3.1 | 27.2 | 21.1 | +7.2 % | 0.4 |
| ned2 Eerste Divisie (Nizozemsko 2) | 760 | 3.11 | 45 % | 44 % | 22 % | 62 % | 58 % | 10.6 | 3.4 | 27.3 | 24.7 | +2.1 % | 0.9 |
| por1 Liga Portugal (Portugalsko) | 612 | 2.63 | 45 % | 42 % | 26 % | 51 % | 48 % | 9.5 | 5.0 | 23.9 | 27.8 | +14.4 % | 0.4 |
| bel1 Jupiler Pro League (Belgie) | 600 | 2.69 | 46 % | 42 % | 28 % | 50 % | 53 % | 10.1 | 3.9 | 26.3 | 22.1 | +6.2 % | 0.9 |
| tur1 Süper Lig (Turecko) | 648 | 2.80 | 44 % | 46 % | 26 % | 54 % | 56 % | 9.6 | 4.7 | 25.4 | 25.9 | +9.0 % | 0.4 |
| sco1 Premiership (Skotsko) | 426 | 2.88 | 45 % | 46 % | 24 % | 57 % | 53 % | 10.5 | 4.0 | 25.3 | 22.8 | +9.1 % | 0.9 |
| aut1 Bundesliga (Rakousko) | 324 | 2.74 | 45 % | 41 % | 25 % | 54 % | 58 % | 9.5 | 4.5 | 24.7 | 22.8 | +1.7 % | 0.9 |
| sui1 Super League (Švýcarsko) | 426 | 3.11 | 43 % | 43 % | 26 % | 61 % | 63 % | 10.3 | 4.5 | 27.6 | 24.6 | +5.1 % | 0.7 |
| den1 Superliga (Dánsko) | 324 | 3.10 | 47 % | 44 % | 26 % | 59 % | 62 % | 9.8 | 3.5 | 26.5 | 22.3 | +4.8 % | 0.7 |
| cze1 Chance Liga (Česko) | 522 | 2.65 | 47 % | 44 % | 23 % | 51 % | 49 % | 10.1 | 3.9 | 25.3 | 24.3 | +7.5 % | 0.7 |
| cze2 Chance Národní liga (Česko 2) | 480 | 2.60 | 47 % | 43 % | 26 % | 50 % | 52 % | 10.4 | 3.9 | 19.0 | – | +2.2 % | 0.4 |
| svk1 Niké liga (Slovensko) | 324 | 2.83 | 46 % | 41 % | 26 % | 56 % | 56 % | 10.1 | 4.4 | 27.0 | 26.8 | +6.2 % | 0.9 |
| pol1 Ekstraklasa (Polsko) | 612 | 2.75 | 47 % | 45 % | 26 % | 51 % | 57 % | 9.9 | 4.1 | 27.6 | 24.6 | +0.6 % | 0.9 |
| gre1 Super League (Řecko) | 412 | 2.51 | 45 % | 42 % | 25 % | 48 % | 48 % | 8.8 | 5.3 | 22.8 | 28.8 | +13.1 % | 0.4 |
| cro1 HNL (Chorvatsko) | 360 | 2.51 | 49 % | 45 % | 28 % | 47 % | 49 % | 9.2 | 4.3 | 22.3 | 25.8 | +7.8 % | 0.9 |
| srb1 Super liga (Srbsko) | 536 | 2.78 | 45 % | 42 % | 26 % | 53 % | 54 % | 9.0 | 4.3 | 24.8 | 28.5 | +8.7 % | 0.4 |
| rou1 Superliga (Rumunsko) | 540 | 2.42 | 46 % | 42 % | 29 % | 43 % | 50 % | 9.5 | 4.2 | 25.6 | 24.0 | +6.9 % | 0.9 |
| hun1 NB I (Maďarsko) | 396 | 2.90 | 44 % | 41 % | 27 % | 56 % | 58 % | 9.7 | 4.6 | 24.6 | 27.6 | +7.9 % | 0.9 |
| nor1 Eliteserien (Norsko) | 480 | 3.01 | 44 % | 45 % | 22 % | 59 % | 55 % | 10.5 | 3.3 | 23.9 | 20.9 | +9.9 % | 0.7 |
| swe1 Allsvenskan (Švédsko) | 480 | 2.84 | 44 % | 43 % | 22 % | 54 % | 54 % | 10.9 | 3.6 | 23.2 | 23.6 | +6.4 % | 0.4 |
| fin1 Veikkausliiga (Finsko) | 309 | 3.17 | 41 % | 43 % | 24 % | 64 % | 61 % | 10.6 | 4.0 | 23.3 | 21.8 | +9.0 % | 0.4 |
| usa1 MLS (USA) | 1005 | 3.08 | 44 % | 44 % | 25 % | 60 % | 62 % | 9.8 | 4.2 | 25.9 | 24.1 | +3.1 % | 0.7 |
| mex1 Liga MX (Mexiko) | 621 | 2.84 | 46 % | 47 % | 24 % | 56 % | 57 % | 9.7 | 4.5 | 25.2 | 24.2 | +6.2 % | 0.7 |
| bra1 Série A (Brazílie) | 760 | 2.48 | 45 % | 49 % | 26 % | 47 % | 50 % | 10.0 | 5.1 | 26.0 | 26.6 | +5.4 % | 0.9 |
| arg1 Liga Profesional (Argentina) | 858 | 1.99 | 45 % | 43 % | 33 % | 32 % | 40 % | 9.0 | 5.2 | 23.7 | 25.0 | +2.3 % | 0.7 |
| jpn1 J1 League (Japonsko) | 578 | 2.57 | 42 % | 48 % | 18 % | 51 % | 50 % | 9.5 | 2.5 | 24.4 | 21.6 | +0.9 % | 0.7 |
| kor1 K League 1 (Jižní Korea) | 426 | 2.62 | 39 % | 44 % | 25 % | 50 % | 54 % | 8.8 | 3.5 | 21.2 | 20.6 | – | – |
| aus1 A-League (Austrálie) | 325 | 3.09 | 45 % | 37 % | 26 % | 60 % | 61 % | 10.1 | 3.5 | 28.1 | 20.2 | – | – |
| ksa1 Saudi Pro League (Saúdská Arábie) | 612 | 2.98 | 43 % | 44 % | 21 % | 57 % | 57 % | 9.9 | 4.2 | 25.0 | 23.6 | – | – |
| chn1 Super League (Čína) | 480 | 3.17 | 46 % | 46 % | 24 % | 60 % | 60 % | 10.3 | 4.0 | 26.7 | 27.2 | – | – |
| ucl Liga mistrů | 288 | 3.32 | 43 % | 51 % | 15 % | 65 % | 53 % | 9.5 | 3.9 | 26.7 | 22.1 | – | – |
| uel Evropská liga | 288 | 2.76 | 45 % | 51 % | 21 % | 53 % | 53 % | 9.3 | 4.4 | 26.0 | 24.4 | – | – |
| uecl Konferenční liga | 216 | 2.67 | 43 % | 52 % | 22 % | 50 % | 49 % | 9.0 | 4.5 | 25.5 | 24.2 | – | – |

## Notes by league / group
- **cze1 Chance Liga** — the richest source of value: Czech books deviate from the international consensus
  far more often than in big leagues (2025/26: 202 closing offers with EV ≥ 1.03 vs 30 in the EPL, ROI +16 %).
  16 teams; after 30 rounds the league splits (title group / relegation) → Livesport stage names, those games
  are still league games. Winter break mid-December → mid-February (ratings carry over; first rounds after the
  break are noisier). Promoted teams start below average (prior).
- **cze2 Chance Národní liga** — no xG on Livesport, thinner international market (few books).
- **eng1 Premier League** — most efficient market; discrepancies rare (≈ 15-30 tier-A bets per season).
  bet365 corner/card lines available on Sofascore for every match.
- **eng2-eng4 (EFL)** — 24 teams, 46 rounds, midweek rounds (rotation), draws 25-27 %. Many matches → many
  chances, but the international consensus is thinner for League One / Two.
- **ita2 Serie B** — the highest draw rate in Europe (32 %), low scoring; under / draw markets.
- **ger1 / ned1 / sui1 / den1 / ger2 / ger3 / ned2** — high scoring (≈ 3.0-3.2 goals), BTTS ≈ 60 %.
- **esp1 / esp2 / por1 / tur1 / gre1 / ita2** — many cards (4.5-5.3 yellows); LaLiga card counts at Livesport
  include situations bookmakers do not count (bench, after the whistle) → card model unreliable there.
- **gre1** — fewest corners (8.8), most fouls.
- **arg1 Argentina** — the lowest-scoring league in the registry (1.99 goals, 33 % draws, only 32 % over 2.5).
- **jpn1** — fewest cards (2.5 yellows per match); **ucl** — most goals (3.3) and fewest draws (15 %).
- **ned1** — fewest cards (3.1).
- **UEFA cups (ucl, uel, uecl)** — consensus only (no model filter); league phase Sep-Jan, knockouts Feb-May;
  watch rotation before / after domestic derbies.
- **Calendar-year leagues** — nor1, swe1, fin1 (season ends Oct-Nov, final rounds = motivation issues),
  usa1 (MLS, playoffs from late Oct), bra1, arg1, kor1, chn1. J1 switched to an autumn-spring calendar in
  2026/27 (spring 2026 was a special half-season).
- **Americas / Asia** run at night or morning CET; scan close to kick-off for team news.
