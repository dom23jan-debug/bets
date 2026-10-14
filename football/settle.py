"""Facts needed to settle football bets of one match: final and half-time score, statistics (corners,
cards, shots ...) and the closing odds of the Czech books (for CLV in the journal).

Usage: python3 -m football.settle <livesport_event_id> ["text of the market label to show closing odds for"]
       python3 -m football.settle --find "<home>" "<away>" <league_key>   (event id from the league cache)
"""
import sys

from .livesport import get, load_cache, match_stats, odds_rows, participants
from .markets import CZ_BOOKS, label
from .names import similarity

STAT_LABELS = (("cor", "rohy"), ("yc", "ŽK"), ("rc", "ČK"), ("sh", "střely"), ("sot", "na branku"),
               ("fo", "fauly"), ("off", "ofsajdy"), ("xg", "xG"))


def halves(event_id):
    """{'1st Half': (home, away), '2nd Half': (home, away)} from the incidents feed."""
    text = get(f"https://local-cz.flashscore.ninja/2/x/feed/df_sui_1_{event_id}", feed=True)
    out = {}
    for rec in text.split("¬~"):
        f = dict(kv.split("÷", 1) for kv in rec.split("¬") if "÷" in kv)
        if "AC" in f and "IG" in f:
            out[f["AC"]] = (int(f["IG"]), int(f["IH"]))
    return out


def main():
    args = sys.argv[1:]
    if args and args[0] == "--find":
        c = load_cache(args[3])
        m = max(c["matches"].values(), key=lambda m: similarity(args[1], m["home"]) + similarity(args[2], m["away"])
                + m["start"] / 1e12)
        print(m["id"], m["home"], "–", m["away"], m.get("home_goals"), ":", m.get("away_goals"))
        return
    eid, wanted = args[0], (args[1] if len(args) > 1 else None)
    hv = halves(eid)
    h1, h2 = hv.get("1st Half"), hv.get("2nd Half")
    if not h1 or not h2:
        print("zápas ještě neskončil / chybí poločasy:", hv)
        return
    print(f"Konečný výsledek {h1[0] + h2[0]}:{h1[1] + h2[1]} (poločas {h1[0]}:{h1[1]}, 2. poločas {h2[0]}:{h2[1]})"
          + ("; prodloužení / penalty: " + str({k: v for k, v in hv.items() if not k.endswith('Half')})
             if len(hv) > 2 else ""))
    st = match_stats(eid)
    print("Statistiky zápas: " + ", ".join(f"{n} {st[f'h_{k}']:g}:{st[f'a_{k}']:g}" for k, n in STAT_LABELS
                                          if f"h_{k}" in st))
    print("Statistiky 1. poločas: " + ", ".join(f"{n} {st[f'h1_{k}']:g}:{st[f'a1_{k}']:g}" for k, n in STAT_LABELS
                                               if f"h1_{k}" in st))
    best = {}
    for r in odds_rows(eid, "CZ", participants(eid)):
        if r[4] in CZ_BOOKS and (r[:4] not in best or r[5] > best[r[:4]][1]):
            best[r[:4]] = (r[4], r[5])
    for k, (book, o) in sorted(best.items(), key=lambda kv: label(kv[0], "domácí", "hosté")):
        text = label(k, "domácí", "hosté")
        if (wanted and wanted.lower() in text.lower()) or (not wanted and k[0] == "HOME_DRAW_AWAY"
                                                           and k[1] == "FULL_TIME"):
            print(f"  zavírací kurz {text}: {o:.2f} ({book})")


if __name__ == "__main__":
    main()
