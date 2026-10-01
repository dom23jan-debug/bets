---
name: hockey-shl
description: Value-bet analysis for SHL (Švédsko) ice hockey (league key `shl`). Use when the user asks for SHL (Švédsko) matches, odds or value bets. Follow the common workflow in the hockey-value skill.
---

# SHL (Švédsko) — league key `shl`

Run: `python3 -m hockey.scan shl <YYYY-MM-DD>` (see skill **hockey-value** for the full procedure).
Tune (monthly / after roster changes): `python3 -m hockey.tune shl` → `data/params.json`.

## Data sources / domains
www.livesport.cz, local-cz.flashscore.ninja, global.ds.lsapp.eu (povinné); shl.se, stats.swehockey.se (oficiální statistiky, sestavy, brankáři).
Livesport path: `/hokej/svedsko/shl/`.

## Format
14 týmů, 52 kol základní části; 3 body za výhru v 60 min, 2/1 za výhru/prohru v prodloužení (3 na 3, 5 min) a nájezdech. Play-off 1.–6. přímo, 7.–10. předkolo; poslední hraje o udržení (HockeyAllsvenskan).

## League profile (regular season 2024/25 + 2025/26, Livesport data)
5,24 gólu/60 min (třetiny 1,53 / 1,81 / 1,90); remízy po 60 min 20,9 %; domácí výhra v 60 min 44,4 %; v prodl./SN vyhrávají domácí 55 %. Vedoucí tým po 2. třetině o 1 gól nevyhraje v 60 min v 33 % případů, o 2 góly v 13 %.

## Quirks & betting notes
Liga s nejnižším skórováním z velkých evropských lig a vysokou vyrovnaností → kurzy na favority bývají přesné, value spíš v totalech a handicapech. Pozor na nováčka z Allsvenskan (krátká historie v datech, model ho táhne k průměru).
