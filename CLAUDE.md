# Hockey + football value betting — instructions for Claude

The user writes in Czech and answers are in Czech. Typical requests: **„najdi mi hokejový value bet"**,
**„najdi mi fotbalový value bet"** (or „co dnes vsadit", „value bety na dnes/zítra", a league or club
name). Treat any such request as the full workflow (hockey below, football in its own section) — no
further questions needed unless a decision is genuinely theirs. „value bet" without a sport = hockey (as
before); football when the request names football (fotbal, a football league / club, rohy, karty ...).

## Hockey workflow („najdi mi hokejový value bet")
1. **Network check** (one command):
   `for u in https://www.livesport.cz https://liiga.fi https://www.shl.se https://api-web.nhle.com/v1/schedule/now; do echo "$u $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -A Mozilla/5.0 $u)"; done`
   Any `000` = blocked by the environment allowlist → tell the user immediately the exact domain line
   to add (bare domain *and* `*.domain`); continue with what works.
2. **Settle open bets** in `journal/bets.csv` (result = win/loss/push/half-win/half-loss, profit_pct):
   look up results on Livesport (`hockey.livesport.league_page`) and fill closing odds if known.
   Show `python3 -m hockey.journal` (ROI, CLV) briefly.
3. **Scan**: `python3 -m hockey.daily [YYYY-MM-DD]` — all European leagues with games that day
   (SHL, DEL, NL, extraliga, Slovensko, Ligue Magnus, Liiga, Maxa liga). For games tonight in North
   America also `python3 nhl_value.py <US date>` (run after ~17:00 CET when goalies are confirmed).
   For Liiga cross-check with `python3 liiga_value.py <date>` (official xG). Daily uses cached data
   in `data/` and refreshes the current season automatically.
4. **Verify every candidate** before recommending (rules in skill `hockey-value`):
   - model vs market gap > 8–10 pp → find the reason (promoted team, goalie, injuries, B-team,
     finishing luck). For SHL use own xG (`data/shl.json` h_xg/a_xg, rebuild `python3 -m hockey.shl_xg`)
     to separate luck from quality. Reject when the underlying numbers contradict the model.
   - one bet per match, prefer lower variance (handicap +1.5 / DNB) when EV is similar;
   - bookmaker-only outliers (value only at one book, model alone not above market) → reject: they lost −15 % in the 2025/26 backtest;
   - early season (< 10 games per team): half of ¼ Kelly, floor 0.5 %, cap 3 %.
5. **Answer** (Czech, concise): ticket table — time, match, bet, odds + bookmaker, EV, „value od"
   (minimum odds), stake % — plus one line „proč" per bet, then rejected candidates in one line each.
   If nothing passes, say clearly „dnes nesázet".
   Then the **Favorit-tiket** from `hockey.daily` (high hit rate, flat 1 % stake, Dominik asked 16 Oct 2026):
   SAFE = winner incl. OT favourite 1.30–1.80, model ≥ market + 4 pp, ≤ 10 games (backtest ~79 % hits);
   FAV = 1X2 60-min favourite 1.40–2.10, model ≥ market (~59 % hits, ROI +8 %, works late season too).
   Verify them like value bets (goalie, injuries); one bet per match across both tickets. Journal with
   market suffix `[SAFE]` / `[FAV]` (e.g. `1X2 60 min [FAV]`) so they can be evaluated separately.
6. **Journal**: append the recommended bets to `journal/bets.csv` with result `open` — skip any bet already
   in the journal for the same date + match (no duplicates when the analysis is re-run the same day).
   Append every rejected candidate (incl. totals) to `journal/rejected.csv` (same columns + reason_cat, reason,
   score_60, odds_source) with the stake it would have got (0.5 % if unknown); settle it together with bets.csv.
7. **Commit & push** changed data/journal/params directly to `main` (the default branch), not to a new branch or PR.

## Football workflow („najdi mi fotbalový value bet", rohy, karty, góly v poločase …) — skill `football-value`
1. **Network check**:
   `for u in https://www.livesport.cz https://global.ds.lsapp.eu https://api.ifortuna.cz/offer/structure/api/v1_0/sports https://api.sofascore.com/api/v1/sport/football/categories; do echo "$u $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -A Mozilla/5.0 $u)"; done`
   (`000` = blocked → give the user the domain lines; the skill's `sources.md` lists what else to add.)
2. **Settle open football bets** like hockey (league keys `eng1`, `cze1`, `ucl` … from `football/leagues.py`;
   results via `football.livesport.league_page(path)`, closing odds via `football.livesport.odds_rows(id)`).
3. **Scan**: `python3 -m football.daily [YYYY-MM-DD]` (all European leagues + UEFA cups with games that day;
   other regions by key, e.g. `... daily <date> usa1 bra1 jpn1`). One league: `python3 -m football.scan <key> <date>`.
   Default ticket = high hit rate (tier A, odds 1.5-2.0, ~57 % won in the backtest); `--vse` = wide ticket (odds ≤ 3.2 + corners/cards).
4. **Verify** every candidate (skill `football-value`: tiers A/B/C, team news via Sofascore/Livesport missing
   players, rotation, referee for cards, price re-check). Value = Czech price above the margin-free consensus of
   ~30-60 international books; the own model must agree. Model-only statistics (shots, fouls, offsides,
   team corners) never go on the ticket. "AP" (second tiers, non-European leagues, UEFA cups > 3 h before kick-off) =
   re-scan ~2 h before kick-off, not a bet yet.
5. **Answer / journal / commit** exactly as for hockey (steps 5-7 above); football bets go to the same
   `journal/bets.csv` / `journal/rejected.csv` with their football league key.

## „Otevři deník" / „ukaž deník" / „jak jsem na tom"
1. Settle open bets first if their matches are finished (step 2 above), commit & push to `main`.
2. `python3 -m hockey.journal --html <scratchpad>/denik.html` → paste the markdown summary
   (Souhrn + open bets; the full list only if asked) into the answer and send the HTML page to the
   user with SendUserFile (display: render) so it opens in the app. If SendUserFile is unavailable,
   paste the full markdown table instead.

## Journal edits and capital (user requests in plain Czech)
- „smaž sázku…", „opravit kurz…", „přidej sázku…", „vsadil jsem jen X": edit `journal/bets.csv`
  directly (keep columns; profit_pct = stake_pct·(odds−1) for win, −stake_pct for loss, 0 for push,
  halves for half-win/half-loss), show the changed rows, commit & push to `main`.
- „nastav kapitál 10 000 Kč" (or a new deposit): write `journal/bankroll.json`
  `{"start": <amount>, "currency": "Kč", "since": "<date>"}`. Stakes and profits stay in % of the
  starting capital (flat staking); the journal shows Kč next to %. When capital is set, every ticket
  also shows the stake in Kč (stake % × current capital from `python3 -m hockey.journal`), rounded
  to 10 Kč. Never change past bets' % when capital changes.

## Maintenance (only when asked or monthly)
- `python3 -m hockey.tune <league ...>` re-tunes hyper-parameters (walk-forward backtest, ~5 min
  per league) → `data/params.json`. Liiga and Maxa use defaults until tuned.
- `python3 -m hockey.odds_hist [league ...] [--season current]` downloads closing odds of finished games
  (`data/odds/`), `python3 -m hockey.market_bt [league ...] --out <file.csv.gz>` backtests model picks
  against them (one row per priced selection with payout) → check which markets / odds bands / phases pay.
- New league: add to `hockey/leagues.py` (Livesport path), run tune, add a `hockey-<key>` skill.
- Football: `python3 -m football.tune <key ...>` (goal model, ~30 s per league → `data/football/params.json`),
  `python3 -m football.odds_hist <key ...> --season 2025-2026` (opening + closing odds, ~4 min per league,
  `data/football/odds/`, not committed), `python3 -m football.market_bt <key ...> --out <f.csv.gz>` then
  `python3 -m football.bt_report <f.csv.gz ...> [--price open]`; corners/cards vs bet365:
  `python3 -m football.stat_bt <key ...>`. New league: add one line to `football/leagues.py`.

## Layout
- `hockey/` shared engine (livesport, model, markets, scan, daily, backtest, tune, journal, shl_xg)
- `football/` football engine (livesport, fortuna, sofascore, model, markets, scan, daily, backtests)
- `.claude/skills/hockey-*` per-league knowledge; `hockey-value` = method and rules;
  `football-value` = football method, rules, sources (`sources.md`) and league notes (`leagues.md`)
- `liiga_value.py`, `maxa_markets.py`, `nhl_value.py` league-specific legacy tools
- `data/` caches and tuned params (committed so new sessions start fast; football in `data/football/`);
  `journal/bets.csv` bet log (hockey and football)
