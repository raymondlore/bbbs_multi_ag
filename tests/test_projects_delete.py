from conftest import API, image_files, make_project, post_project, pw


def test_delete_204(client):
    p, password = make_project(client)
    r = client.delete(f"{API}/projects/{p['id']}", headers=pw(password))
    assert r.status_code == 204 and r.content == b""
    assert client.get(f"{API}/projects/{p['id']}").status_code == 404
    assert client.get(f"{API}/projects").json()["total"] == 0


def test_delete_removes_image_file(client, data_dir):
    r = post_project(client, files=image_files())
    p, password = r.json()["project"], r.json()["edit_password"]
    uploads = data_dir / "uploads"
    before = [f for f in uploads.rglob("*") if f.is_file()]
    assert len(before) == 1
    assert client.delete(f"{API}/projects/{p['id']}", headers=pw(password)).status_code == 204
    assert [f for f in uploads.rglob("*") if f.is_file()] == []
    assert client.get(f"{API}/projects/{p['id']}/image").status_code == 404


def test_delete_cleans_orphan_tags(client):
    p, password = make_project(client, tags=["only-mine", "shared"])
    make_project(client, tags=["shared"])
    client.delete(f"{API}/projects/{p['id']}", headers=pw(password))
    names = {t["name"] for t in client.get(f"{API}/tags").json()["items"]}
    assert names == {"shared"}


def test_delete_missing_password_401(client):
    p, _ = make_project(client)
    for h in (None, {"X-Edit-Password": ""}):
        r = client.delete(f"{API}/projects/{p['id']}", headers=h)
        assert r.status_code == 401 and r.json()["error"]["code"] == "PASSWORD_REQUIRED"
    assert client.get(f"{API}/projects/{p['id']}").status_code == 200


def test_delete_wrong_password_403(client):
    p, _ = make_project(client)
    r = client.delete(f"{API}/projects/{p['id']}", headers=pw("nope"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "PASSWORD_MISMATCH"
    assert client.get(f"{API}/projects/{p['id']}").status_code == 200


def test_delete_404(client):
    r = client.delete(f"{API}/projects/9999", headers=pw("whatever12345"))
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_delete_twice(client):
    p, password = make_project(client)
    client.delete(f"{API}/projects/{p['id']}", headers=pw(password))
    assert client.delete(f"{API}/projects/{p['id']}", headers=pw(password)).status_code == 404
