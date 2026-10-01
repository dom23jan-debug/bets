"""Price bookmaker markets from a score distribution and find +EV selections."""
import collections

NAMES = {"HOME_DRAW_AWAY": "1X2", "DOUBLE_CHANCE": "Dvojitá šance", "DRAW_NO_BET": "Sázka bez remízy",
         "BOTH_TEAMS_TO_SCORE": "Obě dají gól", "OVER_UNDER": "Počet gólů", "ASIAN_HANDICAP": "Handicap",
         "ODD_OR_EVEN": "Lichý/sudý", "HOME_AWAY": "Vítěz"}
SCOPES = {"FULL_TIME": "60 min", "FIRST_PERIOD": "1. třetina", "FULL_TIME_OVER_TIME": "vč. prodl."}


def market_fair_odds(rows):
    """No-vig fair odds per selection (bookmaker margin removed proportionally), averaged across books."""
    groups = collections.defaultdict(list)
    for r in rows:
        bt, scope, sel, line = r[:4]
        key_line = (line if sel == "1" else -line) if bt == "ASIAN_HANDICAP" else line
        groups[(r[4], bt, scope, key_line)].append(r)
    fair = collections.defaultdict(list)
    for (_, bt, _, _), g in groups.items():
        need = 3 if bt in ("HOME_DRAW_AWAY", "DOUBLE_CHANCE") else 2
        if len({(r[2], r[3]) for r in g}) != need:
            continue
        book_sum = sum(1 / r[5] for r in g) / (2 if bt == "DOUBLE_CHANCE" else 1)
        for r in g:
            fair[r[:4]].append(r[5] * book_sum)
    return {k: sum(v) / len(v) for k, v in fair.items()}


def line_prob(dist, value_fn, line):
    if (line * 4) % 2 == 1:  # quarter line = half stake on each neighbouring line
        return ("split", line_prob(dist, value_fn, line - 0.25), line_prob(dist, value_fn, line + 0.25))
    win = sum(p for k, p in dist.items() if value_fn(*k) > line)
    push = sum(p for k, p in dist.items() if value_fn(*k) == line)
    return (win, push)


def expected_return(prob, odds):
    if prob[0] == "split":
        return 0.5 * expected_return(prob[1], odds) + 0.5 * expected_return(prob[2], odds)
    return prob[0] * odds + prob[1]


def win_prob(prob):
    """Probability of a (full or partial) win, for display."""
    if prob[0] == "split":
        return 0.5 * win_prob(prob[1]) + 0.5 * win_prob(prob[2])
    return prob[0]


def with_overtime(ft):
    """Final score incl. OT/SO for totals: a regulation tie adds exactly one decisive goal."""
    out = collections.defaultdict(float)
    for (i, j), p in ft.items():
        if i == j:
            out[(i + 1, j)] += p / 2
            out[(i, j + 1)] += p / 2
        else:
            out[(i, j)] += p
    return out


def model_prob(key, ft, p1, ot_home):
    bt, scope, sel, line = key
    if scope == "FULL_TIME_OVER_TIME":
        if bt == "HOME_AWAY":
            h = sum(p for (i, j), p in ft.items() if i > j)
            x = sum(p for (i, j), p in ft.items() if i == j)
            return (h + x * ot_home, 0) if sel == "1" else (1 - h - x + x * (1 - ot_home), 0)
        if bt == "OVER_UNDER":
            dist = with_overtime(ft)
        else:
            return None
    else:
        dist = p1 if scope == "FIRST_PERIOD" else ft
    h = sum(p for (i, j), p in dist.items() if i > j)
    x = sum(p for (i, j), p in dist.items() if i == j)
    a = 1 - h - x
    if bt == "HOME_DRAW_AWAY":
        return ({"1": h, "X": x, "2": a}[sel], 0)
    if bt == "DOUBLE_CHANCE":
        return ({"1X": h + x, "X2": x + a, "12": h + a}[sel], 0)
    if bt == "DRAW_NO_BET":
        return (h if sel == "1" else a, x)
    if bt == "BOTH_TEAMS_TO_SCORE":
        both = sum(p for (i, j), p in dist.items() if i > 0 and j > 0)
        return (both if sel == "ANO" else 1 - both, 0)
    if bt == "OVER_UNDER":
        if sel == "OVER":
            return line_prob(dist, lambda i, j: i + j, line)
        return line_prob(dist, lambda i, j: -(i + j), -line)
    if bt == "ASIAN_HANDICAP":
        if sel == "1":
            return line_prob(dist, lambda i, j: i - j, -line)
        return line_prob(dist, lambda i, j: j - i, -line)
    if bt == "ODD_OR_EVEN":
        odd = sum(p for (i, j), p in dist.items() if (i + j) % 2)
        return (odd if sel == "ODD" else 1 - odd, 0)
    return None


def label(key, home, away):
    bt, scope, sel, line = key
    text = {"1": home, "2": away}.get(sel, sel)
    if bt == "ASIAN_HANDICAP":
        text = f"{text} {line:+g}"
    elif bt == "OVER_UNDER":
        text = f"{'Více' if sel == 'OVER' else 'Méně'} než {line:g}"
    elif bt == "ODD_OR_EVEN":
        text = {"ODD": "Lichý", "EVEN": "Sudý"}[sel]
    return f"{NAMES.get(bt, bt)} ({SCOPES[scope]}): {text}"


def scan(rows, ft, p1, ot_home, w_model, ev_min=1.03):
    """Return list of dicts for every selection, with blended EV at the best available odds."""
    fair = market_fair_odds(rows)
    best = {}
    for r in rows:
        if r[:4] in fair and (r[:4] not in best or r[5] > best[r[:4]][1]):
            best[r[:4]] = (r[4], r[5])
    out = []
    for key, (book, odds) in best.items():
        prob = model_prob(key, ft, p1, ot_home)
        if prob is None:
            continue
        ev_model = expected_return(prob, odds)
        ev_market = odds / fair[key]
        ev = w_model * ev_model + (1 - w_model) * ev_market
        # odds at which the blended EV would be exactly ev_min (EV is linear in odds for no-push bets)
        out.append({"key": key, "book": book, "odds": odds, "ev": ev, "ev_model": ev_model,
                    "ev_market": ev_market, "p_model": win_prob(prob), "p_market": 1 / fair[key],
                    "min_odds": odds * ev_min / ev if ev > 0 else None})
    return sorted(out, key=lambda o: -o["ev"])


def kelly_quarter(ev, odds, cap=0.03):
    return max(0.0, min(cap, (ev - 1) / (odds - 1) / 4))
