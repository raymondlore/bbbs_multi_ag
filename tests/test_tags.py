import pytest
from conftest import API, make_project, pw


def tags(client):
    r = client.get(f"{API}/tags")
    assert r.status_code == 200
    return r.json()["items"]


def test_empty(client):
    assert client.get(f"{API}/tags").json() == {"items": []}


def test_counts_and_order(client):
    make_project(client, tags=["b", "a", "c"])
    make_project(client, tags=["c", "b"])
    make_project(client, tags=["c"])
    # c:3, b:2, a:1
    assert tags(client) == [{"name": "c", "count": 3}, {"name": "b", "count": 2}, {"name": "a", "count": 1}]


def test_ties_sorted_by_name_asc(client):
    make_project(client, tags=["zeta", "alpha", "mid"])
    assert [t["name"] for t in tags(client)] == ["alpha", "mid", "zeta"]


def test_case_insensitive_merge(client):
    make_project(client, tags=["RAG"])
    make_project(client, tags=["rag"])
    items = tags(client)
    assert len(items) == 1 and items[0]["count"] == 2


def test_only_in_use(client):
    p, password = make_project(client, tags=["x", "y"])
    client.delete(f"{API}/projects/{p['id']}", headers=pw(password))
    assert tags(client) == []


def test_update_removes_unused_tag(client):
    from conftest import base_form
    p, password = make_project(client, tags=["old"])
    client.put(f"{API}/projects/{p['id']}", data=base_form(tags=["new"]), headers=pw(password))
    assert [t["name"] for t in tags(client)] == ["new"]


@pytest.fixture(autouse=True)
def _fast(fast_hash):
    pass
