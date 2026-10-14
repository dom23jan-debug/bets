"""Price football markets from model distributions and from the bookmaker consensus; find +EV offers.

Market keys: (bet_type, scope, selection, line)
  Livesport types: HOME_DRAW_AWAY, DOUBLE_CHANCE, DRAW_NO_BET, ASIAN_HANDICAP, EUROPEAN_HANDICAP, OVER_UNDER,
                   BOTH_TEAMS_TO_SCORE, ODD_OR_EVEN, CORRECT_SCORE, HALF_FULL_TIME
  stat markets (Fortuna): "TOTAL:<stat>" OVER/UNDER, "TEAM:<stat>" "1 OVER"/"2 UNDER"..., "MORE:<stat>" 1/X/2,
                   "EACH:<stat>" ANO/NE with line N (both teams >= N); stat = goals, cor, yc, cards, sh, sot, fo, off
  scope: FULL_TIME, FIRST_HALF, SECOND_HALF

Consensus ("wisdom of the crowd"): every international bookmaker's margin is removed (power method, which
also corrects the favourite-longshot bias), then probabilities are averaged with weights favouring
low-margin (sharper) books. Czech books are excluded from the consensus - they are the ones we bet at.
"""
import collections

from .model import nb_pmf

CZ_BOOKS = ("Tipsport.cz", "iFortuna.cz", "Chance.cz", "Betano.cz", "Fortuna", "Sazka.cz", "Synottip.cz",
            "Merkur.cz", "Forbet.cz", "Kingsbet.cz")
NAMES = {"HOME_DRAW_AWAY": "1X2", "DOUBLE_CHANCE": "Dvojitá šance", "DRAW_NO_BET": "Sázka bez remízy",
         "BOTH_TEAMS_TO_SCORE": "Oba dají gól", "OVER_UNDER": "Počet gólů", "ASIAN_HANDICAP": "Asijský handicap",
         "EUROPEAN_HANDICAP": "Handicap", "ODD_OR_EVEN": "Lichý/sudý", "CORRECT_SCORE": "Přesný výsledek",
         "HALF_FULL_TIME": "Poločas/konec"}
STAT_NAMES = {"goals": "góly", "cor": "rohy", "yc": "žluté karty", "cards": "karty", "sh": "střely",
              "sot": "střely na branku", "fo": "fauly", "off": "ofsajdy"}
SCOPES = {"FULL_TIME": "zápas", "FIRST_HALF": "1. poločas", "SECOND_HALF": "2. poločas"}
N_SEL = {"HOME_DRAW_AWAY": 3, "DOUBLE_CHANCE": 3, "EUROPEAN_HANDICAP": 3, "HALF_FULL_TIME": 9}
NO_CONSENSUS = ("CORRECT_SCORE",)


# ----------------------------------------------------------------------------- margin removal / consensus
def group_line(bt, sel, line):
    if bt == "ASIAN_HANDICAP":
        return line if sel == "1" else -line
    if bt == "EUROPEAN_HANDICAP":
        return line if sel in ("1", "X") else -line
    return line


def devig(odds, target=1.0):
    """Power-method fair probabilities: find k with sum((1/o)^k) = target."""
    q = [1 / o for o in odds]
    if target != 1.0:      # double chance (sum 2): proportional
        s = sum(q)
        return [x * target / s for x in q]
    lo, hi = 0.5, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        if sum(x ** k for x in q) > 1:
            lo = k
        else:
            hi = k
    return [x ** ((lo + hi) / 2) for x in q]


def book_probs(rows, price=5):
    """{(book, key): (p_fair, margin)} for complete market groups of each bookmaker."""
    groups = collections.defaultdict(list)
    for r in rows:
        bt, scope, sel, line, book = r[:5]
        if bt in NO_CONSENSUS:
            continue
        groups[(book, bt, scope, group_line(bt, sel, line))].append(r)
    out = {}
    for (book, bt, _, _), g in groups.items():
        sels = {(r[2], r[3]) for r in g}
        if len(sels) != N_SEL.get(bt, 2) or len(g) != len(sels):
            continue
        odds = [r[price] for r in g]
        target = 2.0 if bt == "DOUBLE_CHANCE" else 1.0
        margin = sum(1 / o for o in odds) / target - 1
        if margin < -0.01 or margin > 0.25:
            continue
        for r, p in zip(g, devig(odds, target)):
            out[(book, r[:4])] = (p, margin)
    return out


def consensus(rows, exclude=CZ_BOOKS, price=5, min_books=3):
    """{key: (p, n_books)} margin-weighted average of no-vig probabilities of non-excluded books."""
    acc = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for (book, key), (p, margin) in book_probs(rows, price).items():
        if book in exclude:
            continue
        w = 1 / (max(margin, 0.0) + 0.015) ** 2
        a = acc[key]
        a[0] += w * p
        a[1] += w
        a[2] += 1
    return {k: (a[0] / a[1], a[2]) for k, a in acc.items() if a[2] >= min_books}


# ----------------------------------------------------------------------------- model probabilities
def line_prob(dist, value_fn, line):
    """(win, push) for 'value > line' with Asian quarter lines split into two halves."""
    if (line * 4) % 2 == 1:
        return ("split", line_prob(dist, value_fn, line - 0.25), line_prob(dist, value_fn, line + 0.25))
    win = sum(p for k, p in dist.items() if value_fn(*k) > line + 1e-9)
    push = sum(p for k, p in dist.items() if abs(value_fn(*k) - line) < 1e-9)
    return (win, push)


def expected_return(prob, odds):
    if prob[0] == "split":
        return 0.5 * expected_return(prob[1], odds) + 0.5 * expected_return(prob[2], odds)
    return prob[0] * odds + prob[1]


def win_prob(prob):
    if prob[0] == "split":
        return 0.5 * win_prob(prob[1]) + 0.5 * win_prob(prob[2])
    return prob[0]


def push_prob(prob):
    if prob[0] == "split":
        return 0.5 * push_prob(prob[1]) + 0.5 * push_prob(prob[2])
    return prob[1]


def htft(h1, h2):
    """Joint distribution of (half-time result, full-time result) assuming independent halves."""
    out = collections.defaultdict(float)
    for (a, b), p in h1.items():
        r1 = "1" if a > b else ("X" if a == b else "2")
        for (c, d), q in h2.items():
            x, y = a + c, b + d
            out[f"{r1}/{'1' if x > y else ('X' if x == y else '2')}"] += p * q
    return out


def goal_market(bt, sel, line, dist):
    h = sum(p for (i, j), p in dist.items() if i > j)
    x = sum(p for (i, j), p in dist.items() if i == j)
    a = 1 - h - x
    if bt == "HOME_DRAW_AWAY":
        return ({"1": h, "X": x, "2": a}[sel], 0.0)
    if bt == "DOUBLE_CHANCE":
        return ({"1X": h + x, "X2": x + a, "12": h + a}[sel], 0.0)
    if bt == "DRAW_NO_BET":
        return (h if sel == "1" else a, x)
    if bt == "BOTH_TEAMS_TO_SCORE":
        both = sum(p for (i, j), p in dist.items() if i > 0 and j > 0)
        return (both if sel == "ANO" else 1 - both, 0.0)
    if bt == "OVER_UNDER":
        if sel == "OVER":
            return line_prob(dist, lambda i, j: i + j, line)
        return line_prob(dist, lambda i, j: -(i + j), -line)
    if bt == "ASIAN_HANDICAP":
        if sel == "1":
            return line_prob(dist, lambda i, j: i - j, -line)
        return line_prob(dist, lambda i, j: j - i, -line)
    if bt == "EUROPEAN_HANDICAP":
        lh = line if sel in ("1", "X") else -line          # home-perspective line
        diff = {"1": lambda i, j: i - j + lh > 0, "X": lambda i, j: i - j + lh == 0,
                "2": lambda i, j: i - j + lh < 0}[sel]
        return (sum(p for (i, j), p in dist.items() if diff(i, j)), 0.0)
    if bt == "ODD_OR_EVEN":
        odd = sum(p for (i, j), p in dist.items() if (i + j) % 2)
        return (odd if sel == "ODD" else 1 - odd, 0.0)
    if bt == "CORRECT_SCORE":
        try:
            i, j = (int(v) for v in sel.split(":"))
        except ValueError:
            return None
        return (dist.get((i, j), 0.0), 0.0)
    return None


def pmf_over(pmf, line, sel):
    """(win, push) of OVER/UNDER line for a 1-D pmf (list index = count)."""
    dist = {(k, 0): p for k, p in enumerate(pmf)}
    if sel == "OVER":
        return line_prob(dist, lambda i, j: i, line)
    return line_prob(dist, lambda i, j: -i, -line)


def stat_dists(mu_h, mu_a, k_team, n_max=60):
    ph = nb_pmf(n_max, mu_h, k_team)
    pa = nb_pmf(n_max, mu_a, k_team)
    return ph, pa


def stat_market(bt, sel, line, sd):
    """sd = {'h': pmf_home, 'a': pmf_away, 't': pmf_total}."""
    kind = bt.split(":")[0]
    if kind == "TOTAL":
        return pmf_over(sd["t"], line, sel)
    if kind == "TEAM":
        side, ou = sel.split()
        return pmf_over(sd["h" if side == "1" else "a"], line, ou)
    joint = None
    if kind in ("MORE", "EACH"):
        joint = {(i, j): p * q for i, p in enumerate(sd["h"]) if p > 1e-7 for j, q in enumerate(sd["a"]) if q > 1e-7}
    if kind == "MORE":
        return goal_market("HOME_DRAW_AWAY", sel, None, joint)
    if kind == "EACH":
        both = sum(p for (i, j), p in joint.items() if i >= line and j >= line)
        return (both if sel == "ANO" else 1 - both, 0.0)
    return None


def model_prob(key, ctx):
    """ctx: {'ft','h1','h2': score dists, 'htft': dict, 'stats': {(stat, scope): sd}}"""
    bt, scope, sel, line = key
    if ":" in bt:
        stat = bt.split(":")[1]
        if stat == "goals":
            dist = ctx[{"FULL_TIME": "ft", "FIRST_HALF": "h1", "SECOND_HALF": "h2"}[scope]]
            sd = goal_pmfs(dist)
        else:
            sd = ctx["stats"].get((stat, scope))
        return stat_market(bt, sel, line, sd) if sd else None
    if bt == "HALF_FULL_TIME":
        return (ctx["htft"].get(sel, 0.0), 0.0) if scope == "FULL_TIME" else None
    dist = ctx.get({"FULL_TIME": "ft", "FIRST_HALF": "h1", "SECOND_HALF": "h2"}.get(scope))
    if dist is None:
        return None
    return goal_market(bt, sel, line, dist)


def goal_pmfs(dist, n=12):
    h, a, t = [0.0] * n, [0.0] * n, [0.0] * (2 * n)
    for (i, j), p in dist.items():
        if i < n and j < n:
            h[i] += p
            a[j] += p
            t[i + j] += p
    return {"h": h, "a": a, "t": t}


# ----------------------------------------------------------------------------- labels / scan
def label(key, home, away):
    bt, scope, sel, line = key
    sc = SCOPES.get(scope, scope)
    if ":" in bt:
        kind, stat = bt.split(":")
        st = STAT_NAMES.get(stat, stat)
        if kind == "TOTAL":
            return f"Počet – {st} ({sc}): {'více' if sel == 'OVER' else 'méně'} než {line:g}"
        if kind == "TEAM":
            side, ou = sel.split()
            return f"{home if side == '1' else away} – {st} ({sc}): {'více' if ou == 'OVER' else 'méně'} než {line:g}"
        if kind == "MORE":
            return f"Více – {st} ({sc}): {({'1': home, '2': away}.get(sel, 'stejně'))}"
        if kind == "EACH":
            return f"Každý tým {line:g}+ – {st} ({sc}): {sel}"
    text = {"1": home, "2": away}.get(sel, sel)
    if bt == "ASIAN_HANDICAP":
        text = f"{text} {line:+g}"
    elif bt == "EUROPEAN_HANDICAP":
        text = f"{text} ({line:+g} {'domácí' if sel in ('1', 'X') else 'hosté'})"
    elif bt == "OVER_UNDER":
        text = f"{'Více' if sel == 'OVER' else 'Méně'} než {line:g}"
    elif bt == "ODD_OR_EVEN":
        text = {"ODD": "Lichý", "EVEN": "Sudý"}[sel]
    return f"{NAMES.get(bt, bt)} ({sc}): {text}"


def scan(rows, cons, ctx, books=CZ_BOOKS, max_odds=15.0):
    """Every offer of the given books at the best price per key, with model EV and consensus EV.

    EV_market uses the consensus fair price (p_c = no-vig probability = P(win | no refund)), so the edge
    only applies to the unrefunded part. Keys without a direct consensus get ev_market None (the scan prices
    them from market-implied goal expectancies or bet365 lines where possible)."""
    best = {}
    for r in rows:
        if r[4] not in books or r[5] > max_odds:
            continue
        if r[:4] not in best or r[5] > best[r[:4]][1]:
            best[r[:4]] = (r[4], r[5])
    out = []
    for key, (book, odds) in best.items():
        prob = model_prob(key, ctx)
        if prob is None:
            continue
        ev_model = expected_return(prob, odds)
        c = cons.get(key)
        if c:
            p_c, n_books = c
            ev_market = 1 + (odds * p_c - 1) * (1 - push_prob(prob))
        else:
            p_c, n_books, ev_market = None, 0, None
        out.append({"key": key, "book": book, "odds": odds, "ev_model": ev_model, "ev_market": ev_market,
                    "ev": ev_market if ev_market is not None else ev_model, "p_model": win_prob(prob),
                    "p_market": p_c, "n_books": n_books, "push": push_prob(prob)})
    return sorted(out, key=lambda o: -o["ev"])


def kelly_stake(ev, odds, cap=0.02, floor=0.005):
    """Quarter Kelly in bankroll fraction, capped; 0 when below the floor would be needed."""
    k = (ev - 1) / (odds - 1) / 4 if odds > 1 else 0.0
    return 0.0 if k <= 0 else max(floor, min(cap, k))
