import re
from conftest import API, JPG, PNG, WEBP, image_files, make_project, post_project

PW_RE = re.compile(r"^[A-Za-z0-9]{12}$")


def test_create_ok(client):
    r = post_project(client, tags=["챗봇", "RAG"])
    assert r.status_code == 201
    body = r.json()
    p = body["project"]
    assert set(p) == {"id", "title", "description", "deploy_url", "repo_url", "author",
                      "tags", "image_url", "created_at", "updated_at"}
    assert p["title"] == "사내 규정 챗봇"
    assert p["deploy_url"] == "http://10.0.0.5:8080"
    assert p["repo_url"] is None
    assert p["author"] == "홍길동"
    assert sorted(p["tags"]) == ["RAG", "챗봇"]
    assert p["image_url"] is None
    assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", p["created_at"])
    assert "edit_password" in body


def test_edit_password_format_and_unique(client):
    _, p1 = make_project(client)
    _, p2 = make_project(client)
    assert PW_RE.match(p1) and PW_RE.match(p2)
    assert not set(p1) & set("0O1lI")
    assert p1 != p2


def test_create_no_store_header(client):
    r = post_project(client)
    assert r.headers["cache-control"] == "no-store"


def test_create_only_repo_url(client):
    r = post_project(client, deploy_url=None, repo_url="https://git.local/a/b")
    assert r.status_code == 201
    assert r.json()["project"]["deploy_url"] is None
    assert r.json()["project"]["repo_url"] == "https://git.local/a/b"


def test_create_with_image(client):
    for content, name, ctype in [(PNG, "a.png", "image/png"), (JPG, "a.jpg", "image/jpeg"),
                                 (WEBP, "a.webp", "image/webp")]:
        r = post_project(client, files=image_files(content, name, ctype))
        assert r.status_code == 201, name
        p = r.json()["project"]
        assert p["image_url"].startswith(f"/api/v1/projects/{p['id']}/image?v=")
        assert client.get(p["image_url"]).status_code == 200


def test_create_dedupes_tags_case_insensitive(client):
    r = post_project(client, tags=["AI", "ai", "Ai", "도구"])
    assert r.status_code == 201
    assert len(r.json()["project"]["tags"]) == 2


def test_create_zero_tags(client):
    assert post_project(client).json()["project"]["tags"] == []


def test_ids_increase(client):
    a, _ = make_project(client)
    b, _ = make_project(client)
    assert b["id"] > a["id"]
