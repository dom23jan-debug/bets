---
name: hockey-del
description: Value-bet analysis for DEL (Německo) ice hockey (league key `del`). Use when the user asks for DEL (Německo) matches, odds or value bets. Follow the common workflow in the hockey-value skill.
---

# DEL (Německo) — league key `del`

Run: `python3 -m hockey.scan del <YYYY-MM-DD>` (see skill **hockey-value** for the full procedure).
Tune (monthly / after roster changes): `python3 -m hockey.tune del` → `data/params.json`.

## Data sources / domains
livesport hosts (povinné); penny-del.org, del.org (sestavy, brankáři, statistiky).
Livesport path: `/hokej/nemecko/del/`.

## Format
14 týmů, 52 kol; bodování 3-2-1-0; prodloužení 3 na 3, nájezdy. Play-off 1.–6., předkolo 7.–10., poslední sestupuje (pokud postupující z DEL2 splní licenci).

## League profile (regular season 2024/25 + 2025/26, Livesport data)
5,92 gólu/60 min (1,78 / 2,10 / 2,05) — nejvíc gólů z velkých lig; remízy po 60 min jen 19,0 %; domácí výhra v 60 min 47,4 %; prodl./SN domácí 51 %. 2. třetina over 2,5 v 35 % zápasů.

## Quirks & betting notes
Hodně import hráčů a velká rotace brankářů — ověřuj startujícího brankáře. Dlouhé cesty (Mnichov–Brémy) a dvojzápasy o víkendu: back-to-back pátek/neděle.
