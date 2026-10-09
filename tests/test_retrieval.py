import math

from app.retrieval import BM25, SearchDocument


def test_bm25_manual_score_and_stable_positive_matches():
    index=BM25([SearchDocument(source_id="b",text="alpha alpha"),SearchDocument(source_id="a",text="beta beta")])
    hits=index.search("alpha")
    expected=math.log(2)*2*2.5/(2+1.5)
    assert len(hits)==1 and hits[0][0]=="b" and math.isclose(hits[0][1],expected)
    assert index.search("unknown")==[] and index.search("")==[]
    ties=BM25([SearchDocument(source_id="b",text="same"),SearchDocument(source_id="a",text="same")])
    assert [key for key,_ in ties.search("same")]==["a","b"]


def test_empty_documents_and_unicode():
    assert BM25([]).search("x")==[]
    assert BM25([SearchDocument(source_id="x",text="")]).search("x")==[]
    assert BM25([SearchDocument(source_id="x",text="CAFÉ")]).search("café")[0][0]=="x"
