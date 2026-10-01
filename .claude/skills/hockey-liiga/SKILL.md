---
name: hockey-liiga
description: Value-bet analysis for Finnish Liiga ice hockey. Use when the user asks for Liiga / finská liga matches, odds or value bets. Follow the common workflow in the hockey-value skill.
---

# Liiga (Finsko)

Two tools:
1. `python3 liiga_value.py <YYYY-MM-DD>` — official liiga.fi API with **per-game expected goals (xG)**
   and Veikkaus odds (best data of all leagues; uses xG 80 % / goals 20 %).
2. `python3 -m hockey.scan liiga <YYYY-MM-DD>` — generic multi-market scan vs Czech bookmakers.
Use (1) for team strength sanity and (2) for the market list; prefer bets where both agree.

## Domains
`liiga.fi`, `*.liiga.fi` (API: https://liiga.fi/api/v2/games?tournament=runkosarja&season=2027,
https://liiga.fi/api/v2/standings/?season=2027) + Livesport hosts.

## Format
2026/27 is a transition season: 17 teams, 64 rounds, places 15–17 relegated directly
(from 2027/28 the 14+10 format). Bodování 3-2-1-0.

## Notes
- League ~5.4 goals/60 min, regulation ties ~23 %; xG differential is the most predictive early-season signal.
- Veikkaus margin ~4.5 %, Czech books 7–9 %.
