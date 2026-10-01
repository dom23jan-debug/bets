"""Bet journal (journal/bets.csv).

  python3 -m hockey.journal              summary + full list (markdown, for chat)
  python3 -m hockey.journal --html PATH  also write a standalone HTML page of the journal
Capital: journal/bankroll.json {"start": 10000, "currency": "Kč"} -> amounts shown next to %.

Columns: date, league, match, market, selection, bookmaker, odds, stake_pct, ev, closing_odds,
result (win/loss/push/half-win/half-loss/open), profit_pct. CLV = odds / closing_odds - 1.
"""
import collections
import csv
import html
import os
import sys

import json

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "journal", "bets.csv")
BANKROLL = os.path.join(os.path.dirname(PATH), "bankroll.json")


def bankroll():
    """Starting capital (flat staking: stake_pct and profit_pct are % of this amount). None = % only."""
    try:
        b = json.load(open(BANKROLL, encoding="utf-8"))
    except (OSError, ValueError):
        return None, "Kč"
    return b.get("start"), b.get("currency", "Kč")


def money(pct, start, cur):
    return f"{pct * start / 100:+,.0f} {cur}".replace(",", " ") if start else ""
RESULT_CZ = {"win": "výhra", "loss": "prohra", "push": "vráceno", "half-win": "½ výhra",
             "half-loss": "½ prohra", "open": "otevřená", "": "otevřená"}


def load():
    return list(csv.DictReader(open(PATH, encoding="utf-8")))


def summary(rows):
    settled = [r for r in rows if r["result"] not in ("", "open")]
    by = collections.defaultdict(lambda: {"n": 0, "won": 0, "stake": 0.0, "profit": 0.0})
    for r in settled:
        for k in ("CELKEM", r["league"]):
            s = by[k]
            s["n"] += 1
            s["won"] += r["result"] in ("win", "half-win")
            s["stake"] += float(r["stake_pct"])
            s["profit"] += float(r["profit_pct"] or 0)
    clv = [float(r["odds"]) / float(r["closing_odds"]) - 1 for r in rows if r["closing_odds"]]
    return by, clv, [r for r in rows if r["result"] in ("", "open")]


def markdown(rows):
    by, clv, open_bets = summary(rows)
    start, cur = bankroll()
    out = ["**Souhrn**", ""]
    if start:
        tot = by.get("CELKEM", {"profit": 0.0})
        open_stake = sum(float(r["stake_pct"]) for r in open_bets)
        out += [f"Kapitál: start {start:,.0f} {cur} → aktuálně **{start * (1 + tot['profit'] / 100):,.0f} {cur}**"
                .replace(",", " ") + f" ({money(tot['profit'], start, cur)}), v otevřených sázkách "
                + f"{open_stake * start / 100:,.0f} {cur}".replace(",", " "), ""]
    out += ["| Liga | Sázek | Výher | Vsazeno | Zisk | ROI |", "|---|---|---|---|---|---|"]
    for k, s in sorted(by.items(), key=lambda kv: (kv[0] != "CELKEM", kv[0])):
        kc = f" ({money(s['profit'], start, cur)})" if start else ""
        out.append(f"| {k} | {s['n']} | {s['won']} | {s['stake']:.2f} % | {s['profit']:+.2f} %{kc} | "
                   f"{100 * s['profit'] / s['stake']:+.1f} % |")
    if clv:
        out.append(f"\nCLV: průměr {100 * sum(clv) / len(clv):+.1f} % ({len(clv)} sázek se zavíracím kurzem)")
    out += ["", f"**Sázky** (otevřené: {len(open_bets)})", "",
            "| Datum | Liga | Zápas | Sázka | Kurz | Vklad | EV | Výsledek | Zisk |", "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: r["date"], reverse=True):
        profit = f"{float(r['profit_pct']):+.2f} %" if r["profit_pct"] else "–"
        stake = f"{r['stake_pct']} %" + (f" ({float(r['stake_pct']) * start / 100:,.0f} {cur})".replace(",", " ")
                                          if start else "")
        out.append(f"| {r['date']} | {r['league']} | {r['match']} | {r['market']}: {r['selection']} | "
                   f"{r['odds']} {r['bookmaker']} | {stake} | {r['ev']} | "
                   f"{RESULT_CZ.get(r['result'], r['result'])} | {profit} |")
    return "\n".join(out)


def html_page(rows):
    by, clv, open_bets = summary(rows)
    tot = by.get("CELKEM", {"n": 0, "won": 0, "stake": 0.0, "profit": 0.0})
    roi = 100 * tot["profit"] / tot["stake"] if tot["stake"] else 0.0
    e = html.escape
    start, cur = bankroll()
    tiles = []
    if start:
        tiles.append(("Kapitál", f"{start * (1 + tot['profit'] / 100):,.0f} {cur}".replace(",", " "),
                      f"start {start:,.0f} {cur}".replace(",", " ")))
    tiles += [("Bilance", f"{tot['profit']:+.2f} %", money(tot["profit"], start, cur) or "bankrollu"), ("ROI", f"{roi:+.1f} %", f"{tot['n']} vyhodnocených"),
             ("Úspěšnost", f"{100 * tot['won'] / tot['n']:.0f} %" if tot["n"] else "–", f"{tot['won']} výher"),
             ("Otevřené", str(len(open_bets)), "čekají na výsledek")]
    if clv:
        tiles.append(("CLV", f"{100 * sum(clv) / len(clv):+.1f} %", f"{len(clv)} sázek"))
    league_rows = "".join(
        f"<tr><td>{e(k)}</td><td>{s['n']}</td><td>{s['won']}</td><td>{s['stake']:.2f} %</td>"
        f"<td class='{'pos' if s['profit'] >= 0 else 'neg'}'>{s['profit']:+.2f} %</td>"
        f"<td>{100 * s['profit'] / s['stake']:+.1f} %</td></tr>"
        for k, s in sorted(by.items()) if k != "CELKEM")
    bet_rows = ""
    for r in sorted(rows, key=lambda r: r["date"], reverse=True):
        res = r["result"] or "open"
        cls = {"win": "pos", "half-win": "pos", "loss": "neg", "half-loss": "neg"}.get(res, "muted")
        profit = f"{float(r['profit_pct']):+.2f} %" if r["profit_pct"] else "–"
        bet_rows += (f"<tr><td>{e(r['date'])}</td><td>{e(r['league'])}</td><td>{e(r['match'])}</td>"
                     f"<td>{e(r['market'])}: <b>{e(r['selection'])}</b></td><td>{e(r['odds'])}<br>"
                     f"<small>{e(r['bookmaker'])}</small></td><td>{e(r['stake_pct'])} %"
                     + (f"<br><small>{float(r['stake_pct']) * start / 100:,.0f} {e(cur)}</small>".replace(",", " ")
                        if start else "") + f"</td><td>{e(r['ev'])}</td>"
                     f"<td><span class='tag {cls}'>{RESULT_CZ.get(res, res)}</span></td>"
                     f"<td class='{cls}'>{profit}</td></tr>")
    tiles_html = "".join(f"<div class='tile'><div class='lab'>{e(a)}</div><div class='val'>{e(b)}</div>"
                         f"<div class='sub'>{e(c)}</div></div>" for a, b, c in tiles)
    return f"""<!doctype html><html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sázkařský deník</title><style>
:root{{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1b;--muted:#6b6b66;--line:#e4e4df;--pos:#1a7f4b;--neg:#c2362b}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151514;--card:#1f1f1d;--fg:#ecece8;--muted:#9a9a93;
--line:#33332f;--pos:#4cc38a;--neg:#ff7b6e}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1000px;margin:0 auto;padding:20px 16px 40px}} h1{{font-size:22px;margin:0 0 4px}}
.muted,small{{color:var(--muted)}} .tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
gap:10px;margin:16px 0}} .tile{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}}
.lab{{color:var(--muted);font-size:13px}} .val{{font-size:22px;font-weight:600}} .sub{{color:var(--muted);font-size:12px}}
h2{{font-size:16px;margin:22px 0 8px}} .wrap{{overflow-x:auto;background:var(--card);border:1px solid var(--line);
border-radius:10px}} table{{border-collapse:collapse;width:100%;min-width:640px}} th,td{{text-align:left;
padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}} th{{font-size:12px;color:var(--muted);
font-weight:600}} tr:last-child td{{border-bottom:0}} .pos{{color:var(--pos)}} .neg{{color:var(--neg)}}
.tag{{font-size:12px;padding:2px 8px;border-radius:99px;border:1px solid currentColor;white-space:nowrap}}
</style></head><body><main><h1>Sázkařský deník</h1>
<div class="muted">Hokejové value bety · vklady v % startovního kapitálu · {len(rows)} sázek</div>
<div class="tiles">{tiles_html}</div>
<h2>Podle ligy</h2><div class="wrap"><table><tr><th>Liga</th><th>Sázek</th><th>Výher</th><th>Vsazeno</th>
<th>Zisk</th><th>ROI</th></tr>{league_rows}</table></div>
<h2>Všechny sázky</h2><div class="wrap"><table><tr><th>Datum</th><th>Liga</th><th>Zápas</th><th>Sázka</th>
<th>Kurz</th><th>Vklad</th><th>EV</th><th>Výsledek</th><th>Zisk</th></tr>{bet_rows}</table></div>
</main></body></html>"""


def main():
    rows = load()
    print(markdown(rows))
    if "--html" in sys.argv:
        path = sys.argv[sys.argv.index("--html") + 1]
        open(path, "w", encoding="utf-8").write(html_page(rows))
        print(f"\nHTML: {path}")


if __name__ == "__main__":
    main()
