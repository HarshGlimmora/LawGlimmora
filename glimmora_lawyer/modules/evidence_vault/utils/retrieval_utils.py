"""Token overlap + lightweight BM25 helpers."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, Iterable, List


_STOPWORDS = set("""
a an and the of to in on for at by with from is are was were be been being
this that these those it its as or if so but not no than then there here
which who whom whose what when where why how do does did has have had will
would can could should may might must shall about into out over under above
below show find list all any some which mention mentions mentioned
""".split())

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/.']*")


def tokenize(text: str, drop_stopwords: bool = True) -> List[str]:
    raw = (text or "").lower()
    toks = _TOKEN_RE.findall(raw)
    if drop_stopwords:
        toks = [t for t in toks if t not in _STOPWORDS and len(t) > 1]
    return toks


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def build_idf(corpus_tokens: List[List[str]]) -> Dict[str, float]:
    """Standard IDF: log((N+1)/(df+1)) + 1, smoothed."""
    df: Counter = Counter()
    for toks in corpus_tokens:
        for t in set(toks):
            df[t] += 1
    n = max(1, len(corpus_tokens))
    return {t: math.log((n + 1) / (df_t + 1)) + 1.0 for t, df_t in df.items()}


def bm25_score(query_toks: List[str], doc_toks: List[str],
               idf: Dict[str, float], avgdl: float,
               k1: float = 1.5, b: float = 0.75) -> float:
    if not query_toks or not doc_toks:
        return 0.0
    dl = len(doc_toks)
    tf = Counter(doc_toks)
    score = 0.0
    for q in query_toks:
        if q not in tf:
            continue
        f = tf[q]
        idf_q = idf.get(q, 1.0)
        score += idf_q * ((f * (k1 + 1)) /
                          (f + k1 * (1 - b + b * (dl / (avgdl or 1)))))
    return score


def normalize_scores(scored: List[tuple[float, dict]]) -> List[tuple[float, dict]]:
    """Linearly map the raw BM25 scores into [0, 1] for display as confidence."""
    if not scored:
        return scored
    top = max(s for s, _ in scored) or 1.0
    return [(s / top, payload) for (s, payload) in scored]
