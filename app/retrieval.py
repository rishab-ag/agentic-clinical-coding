"""Small-corpus BM25 indexing; scores propose context, never confidence."""
from collections import Counter
import math
import re
from typing import List

from app.models import Contract


def tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


class SearchDocument(Contract):
    source_id: str
    text: str


class BM25:
    def __init__(self, documents: List[SearchDocument], k1: float = 1.5, b: float = 0.75):
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("Invalid BM25 parameters")
        if len({d.source_id for d in documents}) != len(documents):
            raise ValueError("Duplicate search document IDs")
        self.documents = documents
        self.k1, self.b = k1, b
        self.counts = [Counter(tokenize(d.text)) for d in documents]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / len(documents) if documents else 0
        self.df = Counter(term for counts in self.counts for term in counts)

    def search(self, query: str, limit: int = 5):
        if limit < 1:
            raise ValueError("Search limit must be positive")
        if not self.average:
            return []
        hits = []
        for document, counts, length in zip(self.documents, self.counts, self.lengths):
            score = 0.0
            for term in set(tokenize(query)):
                tf = counts.get(term, 0)
                if tf:
                    idf = math.log(1 + (len(self.documents) - self.df[term] + 0.5) / (self.df[term] + 0.5))
                    score += idf * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / self.average))
            if score > 0:
                hits.append((document.source_id, score))
        return sorted(hits, key=lambda hit: (-hit[1], hit[0]))[:limit]
