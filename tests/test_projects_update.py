from conftest import API, JPG, PNG, image_files, make_project, post_project, pw


def put(client, pid, password="__none__", files=None, **form):
    from conftest import base_form
    headers = None if password == "__none__" else pw(password)
    return client.put(f"{API}/projects/{pid}", data=base_form(**form), files=files, headers=headers)


def test_full_replace(client):
    p, password = make_project(client, tags=["a", "b"], repo_url="https://g.local/x")
    r = put(client, p["id"], password, title="새 제목", description="새 설명", author="김철수",
            deploy_url=None, repo_url="https://g.local/y", tags=["c"])
    assert r.status_code == 200
    q = r.json()["project"]
    assert q["id"] == p["id"]
    assert q["title"] == "새 제목" and q["author"] == "김철수"
    assert q["deploy_url"] is None and q["repo_url"] == "https://g.local/y"
    assert q["tags"] == ["c"]
    assert q["created_at"] == p["created_at"]
    got = client.get(f"{API}/projects/{p['id']}").json()
    got = got.get("project", got)
    assert got["title"] == "새 제목" and got["tags"] == ["c"]


def test_omitted_fields_cleared(client):
    p, password = make_project(client, tags=["a"], repo_url="https://g.local/x")
    q = put(client, p["id"], password).json()["project"]  # deploy_url만 있는 기본 폼
    assert q["repo_url"] is None and q["tags"] == []


def test_replace_image_and_keep(client):
    r = post_project(client, files=image_files(PNG, "a.png", "image/png"))
    p, password = r.json()["project"], r.json()["edit_password"]
    # 유지
    q = put(client, p["id"], password).json()["project"]
    assert q["image_url"] is not None
    assert client.get(q["image_url"]).status_code == 200
    # 교체
    q2 = put(client, p["id"], password, files=image_files(JPG, "b.jpg", "image/jpeg")).json()["project"]
    img = client.get(q2["image_url"])
    assert img.status_code == 200 and img.content == JPG


def test_remove_image(client):
    r = post_project(client, files=image_files())
    p, password = r.json()["project"], r.json()["edit_password"]
    q = put(client, p["id"], password, remove_image="true")
    assert q.status_code == 200 and q.json()["project"]["image_url"] is None
    assert client.get(f"{API}/projects/{p['id']}/image").status_code == 404


def test_image_and_remove_image_conflict(client):
    r = post_project(client, files=image_files(PNG, "a.png", "image/png"))
    p, password = r.json()["project"], r.json()["edit_password"]
    r2 = put(client, p["id"], password, files=image_files(JPG, "b.jpg", "image/jpeg"), remove_image="true",
             title="바뀌면안됨")
    assert r2.status_code == 422 and r2.json()["error"]["code"] == "VALIDATION_ERROR"
    img = client.get(f"{API}/projects/{p['id']}/image")
    assert img.status_code == 200 and img.content == PNG  # 이미지 그대로
    got = client.get(f"{API}/projects/{p['id']}").json()
    assert got.get("project", got)["title"] == p["title"]


def test_missing_password_401(client):
    p, _ = make_project(client)
    for headers in (None, {"X-Edit-Password": ""}):
        r = client.put(f"{API}/projects/{p['id']}", data={"title": "x"}, headers=headers)
        assert r.status_code == 401 and r.json()["error"]["code"] == "PASSWORD_REQUIRED"


def test_wrong_password_403(client):
    p, _ = make_project(client)
    r = put(client, p["id"], "wrongpassword", title="해킹")
    assert r.status_code == 403 and r.json()["error"]["code"] == "PASSWORD_MISMATCH"
    got = client.get(f"{API}/projects/{p['id']}").json()
    assert got.get("project", got)["title"] == p["title"]


def test_password_in_query_not_accepted(client):
    p, password = make_project(client)
    r = client.put(f"{API}/projects/{p['id']}?edit_password={password}", data={"title": "x"})
    assert r.status_code == 401


def test_not_found_404(client):
    r = put(client, 9999, "whatever12345")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_validation_on_update(client):
    p, password = make_project(client)
    r = put(client, p["id"], password, title="  ")
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = put(client, p["id"], password, deploy_url=None)  # URL 둘 다 없음
    assert r.status_code == 422
