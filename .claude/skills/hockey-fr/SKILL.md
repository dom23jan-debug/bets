---
name: hockey-fr
description: Value-bet analysis for Ligue Magnus (Francie) ice hockey (league key `fr`). Use when the user asks for Ligue Magnus (Francie) matches, odds or value bets. Follow the common workflow in the hockey-value skill.
---

# Ligue Magnus (Francie) — league key `fr`

Run: `python3 -m hockey.scan fr <YYYY-MM-DD>` (see skill **hockey-value** for the full procedure).
Tune (monthly / after roster changes): `python3 -m hockey.tune fr` → `data/params.json`.

## Data sources / domains
livesport hosts (povinné); liguemagnus.com, hockeyfrance.com (sestavy, statistiky).
Livesport path: `/hokej/francie/ligue-magnus/`.

## Format
12 týmů, 44 kol; bodování 3-2-1-0; play-off 1.–8.; poslední dva hrají o udržení.

## League profile (regular season 2024/25 + 2025/26, Livesport data)
6,00 gólu/60 min (1,77 / 2,13 / 2,10) — nejvíce gólů; nejsilnější domácí výhoda (3,27 vs 2,74); remízy po 60 min 19,7 %. 2. třetina over 1,5 v 63,8 % a over 2,5 v 36,7 % (nejvíc ze všech lig); 3. třetina s ≥3 góly ve 34 %. Obrat z −2 po 2. třetině 17,4 % (2. nejvíc po Slovensku).

## Quirks & betting notes
Hypotéza uživatele potvrzena daty: vysoké skórování ve 2. a 3. třetině a časté obraty. Livesport nevede kurzy na 2./3. třetinu → využití hlavně LIVE (např. tým prohrávající o 2 po 2. třetině neprohraje v 60 min v 17 % → férový kurz ~5,7; live kurzy bývají vyšší). Statistiky střel jen u části zápasů → model hlavně z gólů, w_model 0,5.
