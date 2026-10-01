---
name: hockey-maxa
description: Value-bet analysis for Czech Maxa liga (2nd tier) ice hockey. Use when the user asks for Maxa liga / 1. liga matches, odds or value bets. Follow the common workflow in the hockey-value skill.
---

# Maxa liga (Česko, 2. liga)

Run: `python3 -m hockey.scan maxa <YYYY-MM-DD>` (generic) or legacy `python3 maxa_markets.py <date>`.

## Domains
Livesport hosts only (hokej.cz geoblocks foreign IPs).

## Notes
- ~5.4 goals/60 min, regulation ties ~23 %; Czech books' totals lines tend to sit above the league mean
  (5.5–6) → unders in low-scoring teams' games were the recurring value in Sept 2026.
- B-teams of extraliga clubs (e.g. Pardubice B) have volatile rosters: model–market gaps there are
  often information, not value → prefer +1.5 handicaps over outrights, smaller stakes.
- Preseason prior (title/relegation odds) matters a lot in the first 10 rounds.
