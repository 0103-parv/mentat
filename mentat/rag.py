"""Grounded QA (RAG) — the honest cure for an AI "going hazy".

The fix for blurriness is NOT to lobotomize the model down to one domain — it is to
GROUND every answer in a real corpus and REFUSE to answer beyond it. This is the
verification gate applied to question-answering: retrieve the relevant source passages,
answer ONLY from them with citations, and say "I don't have a grounded source" rather
than guess. No source -> no claim.

Pure-Python BM25 retrieval (no deps) over a folder of finance docs (.md/.txt). With a
reasoning core it synthesizes a cited answer strictly from the retrieved passages;
offline it returns the top passage verbatim with its source. Either way it cites, and
either way it refuses when retrieval is too weak — that refusal is the anti-haze guarantee.

  python3 -m mentat.rag "what is the deflated sharpe ratio?"
  python3 -m mentat.rag "who won the 2010 world cup?"     # -> refuses (not in corpus)
"""
from __future__ import annotations

import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

DOCS_DIR = Path(__file__).parent / "finance_docs"
MIN_SCORE = 1.5          # below this, retrieval is too weak -> refuse rather than guess


def _tok(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def _chunk(text: str, doc: str, max_words: int = 90) -> list[tuple[str, str]]:
    """Split a doc into passages (by paragraph, then capped by word count)."""
    out: list[tuple[str, str]] = []
    for para in re.split(r"\n\s*\n", text.strip()):
        words = para.split()
        if not words:
            continue
        for i in range(0, len(words), max_words):
            out.append((doc, " ".join(words[i:i + max_words])))
    return out


@dataclass
class Rag:
    passages: list[tuple[str, str]]            # (doc, text)
    use_embeddings: bool = True                 # hybrid BM25 + embedding cosine ranking

    def __post_init__(self):
        self.toks = [_tok(t) for _, t in self.passages]
        self.N = len(self.passages)
        self.avgdl = sum(len(t) for t in self.toks) / max(1, self.N)
        self.df: dict[str, int] = {}
        for tk in self.toks:
            for w in set(tk):
                self.df[w] = self.df.get(w, 0) + 1
        self._pvecs = None                      # lazily-computed passage embeddings

    def _ensure_vecs(self) -> None:
        if self._pvecs is None:
            from .embed import embed
            self._pvecs = embed([t for _, t in self.passages])

    @classmethod
    def from_dir(cls, path: Path | str = DOCS_DIR) -> "Rag":
        path = Path(path)
        passages: list[tuple[str, str]] = []
        for f in sorted(path.glob("*.md")) + sorted(path.glob("*.txt")):
            passages.extend(_chunk(f.read_text(encoding="utf-8"), f.stem))
        if not passages:
            raise ValueError(f"no documents found under {path}")
        return cls(passages)

    def _idf(self, w: str) -> float:
        n = self.df.get(w, 0)
        return math.log(1 + (self.N - n + 0.5) / (n + 0.5))

    def _score(self, q: list[str], i: int, k1: float = 1.5, b: float = 0.75) -> float:
        tf = Counter(self.toks[i])
        dl = len(self.toks[i])
        s = 0.0
        for w in q:
            f = tf.get(w, 0)
            if f:
                s += self._idf(w) * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / self.avgdl))
        return s

    def retrieve(self, query: str, k: int = 4) -> list[tuple[float, str, str]]:
        """Hybrid ranking: normalized BM25 + normalized embedding cosine. The returned
        score is the BM25 (lexical) score, which `answer` uses to guard refusal — so
        embeddings improve RANKING while grounding stays lexically anchored (anti-haze)."""
        q = _tok(query)
        bm = [self._score(q, i) for i in range(self.N)]
        rank = list(bm)
        if self.use_embeddings:
            try:
                from .embed import cosine, embed
                self._ensure_vecs()
                qv = embed([query])[0]
                cos = [max(0.0, cosine(qv, self._pvecs[i])) for i in range(self.N)]
                bmax, cmax = (max(bm) or 1.0), (max(cos) or 1.0)
                rank = [bm[i] / bmax + cos[i] / cmax for i in range(self.N)]
            except Exception:
                rank = list(bm)
        order = sorted(range(self.N), key=lambda i: rank[i], reverse=True)[:k]
        return [(bm[i], self.passages[i][0], self.passages[i][1]) for i in order if rank[i] > 0]

    def answer(self, query: str, *, core=None, min_score: float = MIN_SCORE) -> dict:
        """Grounded answer or honest refusal. `core` (a reasoning core) synthesizes a
        cited answer from the passages; without one, return the top passage verbatim."""
        hits = self.retrieve(query, k=4)
        if not hits or hits[0][0] < min_score:
            return {"grounded": False,
                    "answer": "I don't have a grounded source for that in the corpus, "
                              "so I won't guess.",
                    "sources": []}
        sources = [{"doc": d, "score": round(s, 2), "text": t} for s, d, t in hits]
        if core is not None:
            ctx = "\n\n".join(f"[{i + 1}] ({h['doc']}) {h['text']}"
                              for i, h in enumerate(sources))
            sys_p = ("Answer ONLY from the numbered sources, citing them as [n]. Use no "
                     "outside knowledge. If the sources do not answer the question, say "
                     "'the sources don't cover that.' Be concise.")
            try:
                ans = core.complete_text(sys_p, f"Sources:\n{ctx}\n\nQuestion: {query}",
                                         max_tokens=400)
            except Exception:
                ans = sources[0]["text"]
        else:
            ans = sources[0]["text"]
        return {"grounded": True, "answer": ans, "sources": sources}


def main() -> int:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print('usage: python3 -m mentat.rag "<finance question>"')
        return 1
    rag = Rag.from_dir()
    core = None
    try:
        from .reasoning import AnthropicCore, core_available
        if core_available():
            core = AnthropicCore()
    except Exception:
        pass
    res = rag.answer(query, core=core)
    print(f"Q: {query}\n")
    print(res["answer"])
    if res["sources"]:
        print("\nsources:")
        for s in res["sources"]:
            print(f"  [{s['doc']}] (score {s['score']})")
    else:
        print("\n(no grounded source — refused rather than hallucinate)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
