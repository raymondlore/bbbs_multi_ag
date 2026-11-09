import pytest
import math
from conftest import API, make_project


def lst(client, **params):
    r = client.get(f"{API}/projects", params=params)
    return r


def test_empty(client):
    r = lst(client)
    assert r.status_code == 200
    assert r.json() == {"items": [], "page": 1, "page_size": 20, "total": 0}


def test_item_shape(client):
    make_project(client, tags=["a"])
    it = lst(client).json()["items"][0]
    assert set(it) == {"id", "title", "summary", "author", "tags", "image_url", "created_at"}
    assert "has_image" not in it and "description" not in it


def test_summary_150(client):
    make_project(client, description="가" * 500)
    s = lst(client).json()["items"][0]["summary"]
    assert s.startswith("가" * 150)
    assert len(s) <= 153  # 말줄임표 허용


def test_sorted_newest_first(client):
    ids = [make_project(client, title=f"t{i}")[0]["id"] for i in range(5)]
    got = [i["id"] for i in lst(client).json()["items"]]
    assert got == sorted(ids, reverse=True)


def test_pagination(client):
    for i in range(23):
        make_project(client, title=f"t{i}")
    r1 = lst(client).json()
    assert r1["total"] == 23 and len(r1["items"]) == 20 and r1["page_size"] == 20
    r2 = lst(client, page=2).json()
    assert len(r2["items"]) == 3 and r2["page"] == 2
    assert not {i["id"] for i in r1["items"]} & {i["id"] for i in r2["items"]}
    assert math.ceil(r1["total"] / r1["page_size"]) == 2


def test_page_size(client):
    for i in range(7):
        make_project(client)
    assert len(lst(client, page_size=3).json()["items"]) == 3
    assert lst(client, page_size=50).status_code == 200


def test_invalid_paging_422(client):
    for params in [{"page": 0}, {"page": -1}, {"page": "x"}, {"page_size": 51}, {"page_size": 0}]:
        r = lst(client, **params)
        assert r.status_code == 422, params
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_page_out_of_range(client):
    make_project(client)
    r = lst(client, page=99)
    assert r.status_code == 200
    assert r.json()["items"] == [] and r.json()["total"] == 1


def test_q_title_and_description(client):
    make_project(client, title="챗봇 서비스", description="설명A")
    make_project(client, title="다른것", description="문서 검색 엔진")
    make_project(client, title="무관", description="무관")
    assert lst(client, q="챗봇").json()["total"] == 1
    assert lst(client, q="검색").json()["total"] == 1
    assert lst(client, q="없는말").json()["total"] == 0


def test_q_wildcards_literal(client):
    make_project(client, title="100% 완성", description="x")
    make_project(client, title="abc", description="y")
    make_project(client, title="a_c", description="z")
    assert lst(client, q="%").json()["total"] == 1
    assert lst(client, q="_").json()["total"] == 1
    assert lst(client, q="\\").json()["total"] == 0


def test_q_too_long_422(client):
    assert lst(client, q="a" * 101).status_code == 422
    assert lst(client, q="a" * 100).status_code == 200


def test_tag_filter_exact_case_insensitive(client):
    make_project(client, title="p1", tags=["RAG", "챗봇"])
    make_project(client, title="p2", tags=["챗봇"])
    make_project(client, title="p3", tags=["RAGX"])
    assert lst(client, tag="rag").json()["total"] == 1
    assert lst(client, tag="챗봇").json()["total"] == 2
    assert lst(client, tag="RA").json()["total"] == 0
    item = lst(client, tag="rag").json()["items"][0]
    assert sorted(item["tags"]) == ["RAG", "챗봇"]  # 필터해도 전체 태그 표시


def test_q_and_tag_combined(client):
    make_project(client, title="챗봇A", tags=["x"])
    make_project(client, title="챗봇B", tags=["y"])
    assert lst(client, q="챗봇", tag="x").json()["total"] == 1


@pytest.fixture(autouse=True)
def _fast(fast_hash):
    pass
