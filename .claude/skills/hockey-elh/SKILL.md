---
name: hockey-elh
description: Value-bet analysis for Tipsport extraliga (Česko) ice hockey (league key `elh`). Use when the user asks for Tipsport extraliga (Česko) matches, odds or value bets. Follow the common workflow in the hockey-value skill.
---

# Tipsport extraliga (Česko) — league key `elh`

Run: `python3 -m hockey.scan elh <YYYY-MM-DD>` (see skill **hockey-value** for the full procedure).
Tune (monthly / after roster changes): `python3 -m hockey.tune elh` → `data/params.json`.

## Data sources / domains
livesport hosts (povinné). hokej.cz a tipsportextraliga.cz blokují zahraniční IP (403) — nepoužitelné z cloudu.
Livesport path: `/hokej/cesko/extraliga/`.

## Format
14 týmů, 52 kol; bodování 3-2-1-0; play-off 1.–6., předkolo 7.–10.; poslední hraje baráž s vítězem Maxa ligy.

## League profile (regular season 2024/25 + 2025/26, Livesport data)
5,09 gólu/60 min (1,50 / 1,82 / 1,77) — nejméně gólů; remízy po 60 min 21,6 %; domácí výhra v 60 min 46,7 %; prodl./SN domácí 59 % (nejvíc). Vedoucí o 1 po 2. třetině nevyhraje v 60 min ve 40 %.

## Quirks & betting notes
Nejnižší skórování → under linie 5,5 je pro trh typická; pozor na brankáře (často rozhodují). Kluby posílají hráče do Maxa ligy (farmy) — kádr se mění.
