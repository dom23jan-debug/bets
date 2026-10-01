---
name: hockey-nl
description: Value-bet analysis for National League (Švýcarsko) ice hockey (league key `nl`). Use when the user asks for National League (Švýcarsko) matches, odds or value bets. Follow the common workflow in the hockey-value skill.
---

# National League (Švýcarsko) — league key `nl`

Run: `python3 -m hockey.scan nl <YYYY-MM-DD>` (see skill **hockey-value** for the full procedure).
Tune (monthly / after roster changes): `python3 -m hockey.tune nl` → `data/params.json`.

## Data sources / domains
livesport hosts (povinné); nationalleague.ch, data.sihf.ch (oficiální data SIHF).
Livesport path: `/hokej/svycarsko/national-league/`.

## Format
14 týmů, 52 kol; bodování 3-2-1-0; play-off 1.–6., play-in 7.–10.; poslední hraje baráž se šampionem Swiss League.

## League profile (regular season 2024/25 + 2025/26, Livesport data)
5,27 gólu/60 min (1,53 / 1,81 / 1,93); remízy po 60 min 23,5 % (nejvíc); silná domácí výhoda (2,93 vs 2,34 gólu); prodl./SN domácí 53 %. Obraty: vedoucí o 1 po 2. třetině nevyhraje v 60 min ve 40 %.

## Quirks & betting notes
Limit 6 cizinců na soupisce (4 hrají) — zranění importu má velký dopad. Remízy po 60 min jsou časté → 1X2 remíza bývá podceněná.
