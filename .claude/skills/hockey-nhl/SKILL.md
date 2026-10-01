---
name: hockey-nhl
description: Value-bet analysis for NHL ice hockey. Use when the user asks for NHL matches, odds or value bets. Follow the common workflow in the hockey-value skill.
---

# NHL

Run: `python3 nhl_value.py <YYYY-MM-DD>` (NHL date = US date; games are at night CET).

## Model
Roster-based ratings (current rosters from NHL API × each player's previous-season on-ice xG/60 from
MoneyPuck) blended with last season's team xG; starting goalies from DailyFaceoff with **two-season**
GSAx/60 (single seasons mislead — Stolarz case); back-to-back penalty; score model with empty-net
phase fitted to 1,312 games of 2025/26 (24.8 % regulation ties, OT home share 49 %).
w_model 0.4 — NHL lines are the sharpest; expect few bets.

## Domains
`api-web.nhle.com`, `api.nhle.com`, `moneypuck.com`, `*.moneypuck.com`, `www.dailyfaceoff.com`
(+ Livesport hosts). Note `*.domain` does not cover the bare domain.

## Notes
- Run after goalies are confirmed (~17–19 h CET).
- 2026/27 regular season started 29 Sep 2026.
