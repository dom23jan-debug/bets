"""Team-name matching between Livesport (Czech names), Fortuna and Sofascore (English names)."""
import difflib
import re
import unicodedata

DROP = {"fc", "fk", "sk", "ac", "as", "afc", "cf", "sc", "ssc", "bk", "if", "ik", "cd", "ud", "sd", "rc", "rcd",
        "vfb", "vfl", "tsg", "sv", "fsv", "1", "club", "de", "the", "calcio", "spor", "kulubu", "ii", "u23", "u21"}
ALIAS = {"utd": "united", "man": "manchester", "ml": "mlada", "nottingham": "nottingham forest",
         "wolves": "wolverhampton", "spurs": "tottenham", "psg": "paris saint germain", "inter": "internazionale",
         "bayern": "bayern munchen", "mnichov": "munchen", "praha": "prague", "plzen": "viktoria plzen"}


def norm(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s.replace(".", " "))
    words = [ALIAS.get(w, w) for w in s.split()]
    words = [w for w in " ".join(words).split() if w not in DROP]
    return " ".join(words)


def similarity(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    r = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    if ta & tb:
        r = max(r, 0.6 + 0.4 * len(ta & tb) / max(len(ta), len(tb)))
    if na in nb or nb in na:
        r = max(r, 0.85)
    return r


def match_pair(home, away, candidates, key=lambda c: (c["home"], c["away"]), min_score=1.2):
    """Best candidate whose (home, away) names resemble the given pair (sum of similarities)."""
    best = None
    for c in candidates:
        h, a = key(c)
        s = similarity(home, h) + similarity(away, a)
        if best is None or s > best[0]:
            best = (s, c)
    return best[1] if best and best[0] >= min_score else None
