---
name: hockey-sk
description: Value-bet analysis for Tipsport liga (Slovensko) ice hockey (league key `sk`). Use when the user asks for Tipsport liga (Slovensko) matches, odds or value bets. Follow the common workflow in the hockey-value skill.
---

# Tipsport liga (Slovensko) — league key `sk`

Run: `python3 -m hockey.scan sk <YYYY-MM-DD>` (see skill **hockey-value** for the full procedure).
Tune (monthly / after roster changes): `python3 -m hockey.tune sk` → `data/params.json`.

## Data sources / domains
livesport hosts (povinné); hockeyslovakia.sk, tiposextraliga.sk (oficiální statistiky).
Livesport path: `/hokej/slovensko/extraliga/`.

## Format
12 týmů; čtyřkolově (cca 50 kol); bodování 3-2-1-0; play-off 1.–8.; poslední hraje baráž.

## League profile (regular season 2024/25 + 2025/26, Livesport data)
5,71 gólu/60 min (1,65 / 2,01 / 2,04); remízy po 60 min 22,2 %; domácí výhra v 60 min 43,4 %. Obraty z −2 po 2. třetině ve 20,8 % (nejvíc ze všech lig).

## Quirks & betting notes
Statistiky střel na Livesportu jen u části zápasů → model stojí hlavně na gólech, proto w_model 0,5 a menší vklady. Velké rozdíly v kvalitě kádrů, kurzy méně přesné než v top ligách.
