# Hockey value betting — instructions for Claude

The user writes in Czech and answers are in Czech. Typical request: **„najdi mi hokejový value bet"**
(or „co dnes vsadit", „value bety na dnes/zítra", a league name). Treat any such request as the
full workflow below — no further questions needed unless a decision is genuinely theirs.

## Workflow for „najdi mi value bet"
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
   - bookmaker-only outliers (value only at one book) are fine but name the book;
   - early season (< 10 games per team): half of ¼ Kelly, floor 0.5 %, cap 3 %.
5. **Answer** (Czech, concise): ticket table — time, match, bet, odds + bookmaker, EV, „value od"
   (minimum odds), stake % — plus one line „proč" per bet, then rejected candidates in one line each.
   If nothing passes, say clearly „dnes nesázet".
6. **Journal**: append the recommended bets to `journal/bets.csv` with result `open`.
7. **Commit & push** changed data/journal/params directly to `main` (the default branch), not to a new branch or PR.

## Maintenance (only when asked or monthly)
- `python3 -m hockey.tune <league ...>` re-tunes hyper-parameters (walk-forward backtest, ~5 min
  per league) → `data/params.json`. Liiga and Maxa use defaults until tuned.
- New league: add to `hockey/leagues.py` (Livesport path), run tune, add a `hockey-<key>` skill.

## Layout
- `hockey/` shared engine (livesport, model, markets, scan, daily, backtest, tune, journal, shl_xg)
- `.claude/skills/hockey-*` per-league knowledge; `hockey-value` = method and rules
- `liiga_value.py`, `maxa_markets.py`, `nhl_value.py` league-specific legacy tools
- `data/` caches and tuned params (committed so new sessions start fast); `journal/bets.csv` bet log
