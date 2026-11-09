from conftest import API, image_files, make_project, post_project


def test_detail_fields(client):
    created, _ = make_project(client, tags=["a", "b"], repo_url="https://g.local/x")
    r = client.get(f"{API}/projects/{created['id']}")
    assert r.status_code == 200
    assert r.json() == {"project": created} or r.json() == created
    p = r.json().get("project", r.json())
    assert set(p) == {"id", "title", "description", "deploy_url", "repo_url", "author",
                      "tags", "image_url", "created_at", "updated_at"}


def test_detail_not_found(client):
    r = client.get(f"{API}/projects/9999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_detail_non_int_id_422_or_404(client):
    r = client.get(f"{API}/projects/abc")
    assert r.status_code in (404, 422)
    assert "error" in r.json()


def test_no_password_fields(client):
    created, password = make_project(client)
    text = client.get(f"{API}/projects/{created['id']}").text
    assert password not in text
    for bad in ("password", "hash", "salt", "image_filename"):
        assert bad not in text.lower()


def test_list_has_no_password(client):
    _, password = make_project(client)
    text = client.get(f"{API}/projects").text
    assert password not in text and "password" not in text.lower() and "hash" not in text.lower()


def test_detail_image_url(client):
    r = post_project(client, files=image_files())
    pid = r.json()["project"]["id"]
    p = client.get(f"{API}/projects/{pid}").json()
    p = p.get("project", p)
    assert p["image_url"].startswith(f"/api/v1/projects/{pid}/image?v=")
