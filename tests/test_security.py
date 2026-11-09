import pytest
from conftest import API, make_project, post_project, pw

CSP = "default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'"


def assert_headers(r):
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("content-security-policy") == CSP


def test_security_headers_everywhere(client):
    p, password = make_project(client, files=None)
    responses = [
        client.get(f"{API}/projects"),
        client.get(f"{API}/projects/{p['id']}"),
        client.get(f"{API}/tags"),
        client.get(f"{API}/projects/9999"),            # 404
        client.get(f"{API}/nonexistent"),              # 404 라우트 없음
        client.patch(f"{API}/projects/{p['id']}"),     # 405
        client.get(f"{API}/projects?page=0"),          # 422
        client.delete(f"{API}/projects/{p['id']}"),    # 401
        post_project(client),                          # 201
    ]
    for r in responses:
        assert_headers(r)


def test_security_headers_on_image(client):
    from conftest import image_files
    p = post_project(client, files=image_files()).json()["project"]
    assert_headers(client.get(f"{API}/projects/{p['id']}/image"))


def test_error_format_404_route(client):
    r = client.get(f"{API}/nope")
    assert r.status_code == 404
    e = r.json()["error"]
    assert e["code"] == "NOT_FOUND" and isinstance(e["message"], str) and e["message"]


def test_error_format_405(client):
    r = client.patch(f"{API}/projects/1")
    assert r.status_code == 405 and r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    r = client.put(f"{API}/tags")
    assert r.status_code == 405 and r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_error_format_422_has_no_detail(client):
    r = client.get(f"{API}/projects?page=abc")
    assert r.status_code == 422
    body = r.json()
    assert set(body) == {"error"} and "detail" not in body
    assert set(body["error"]) == {"code", "message"}


def test_error_format_all_codes_shape(client):
    p, _ = make_project(client)
    for r in [client.get(f"{API}/projects/9999"), client.delete(f"{API}/projects/{p['id']}"),
              client.delete(f"{API}/projects/{p['id']}", headers=pw("x")),
              post_project(client, title="")]:
        body = r.json()
        assert set(body) == {"error"} and set(body["error"]) == {"code", "message"}


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/api/v1/docs", "/api/v1/openapi.json"])
def test_docs_disabled(client, path):
    r = client.get(path)
    assert r.status_code == 404
    assert "swagger" not in r.text.lower() and '"openapi"' not in r.text


SQLI = ["' OR '1'='1", "'; DROP TABLE projects; --", "\" OR 1=1 --", "x' UNION SELECT password_hash FROM projects--"]


@pytest.mark.parametrize("s", SQLI)
def test_sql_injection_in_query_params(client, s):
    make_project(client, title="정상 과제", tags=["a"])
    r = client.get(f"{API}/projects", params={"q": s})
    assert r.status_code == 200 and r.json()["total"] == 0
    r = client.get(f"{API}/projects", params={"tag": s})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert client.get(f"{API}/projects").json()["total"] == 1  # 테이블 멀쩡


@pytest.mark.parametrize("s", SQLI)
def test_sql_injection_stored_literally(client, s):
    p, password = make_project(client, title=s[:100], description=s, author=s[:30])
    got = client.get(f"{API}/projects/{p['id']}").json()
    got = got.get("project", got)
    assert got["title"] == s[:100] and got["description"] == s
    assert client.get(f"{API}/projects").json()["total"] == 1


def test_sql_injection_in_password_header(client):
    p, _ = make_project(client)
    r = client.delete(f"{API}/projects/{p['id']}", headers=pw("' OR '1'='1"))
    assert r.status_code == 403
    assert client.get(f"{API}/projects/{p['id']}").status_code == 200


def test_sql_injection_in_path(client):
    r = client.get(f"{API}/projects/1 OR 1=1")
    assert r.status_code in (404, 422)


def test_html_stored_as_text_not_altered(client):
    xss = "<script>alert(1)</script>"
    p, _ = make_project(client, title=xss, description=xss)
    got = client.get(f"{API}/projects/{p['id']}").json()
    assert got.get("project", got)["title"] == xss  # 출력 이스케이프는 클라이언트 책임(textContent)


def test_no_hash_or_password_in_any_response(client):
    p, password = make_project(client, tags=["t"])
    texts = [client.get(f"{API}/projects").text, client.get(f"{API}/projects/{p['id']}").text,
             client.get(f"{API}/tags").text]
    from conftest import base_form
    texts.append(client.put(f"{API}/projects/{p['id']}", data=base_form(), headers=pw(password)).text)
    for t in texts:
        assert password not in t
        low = t.lower()
        assert "password" not in low and "hash" not in low and "pbkdf2" not in low and "salt" not in low


def test_password_stored_hashed(client, data_dir):
    import sqlite3
    _, password = make_project(client)
    con = sqlite3.connect(data_dir / "app.db")
    rows = con.execute("select password_hash from projects").fetchall()
    con.close()
    assert rows and password not in rows[0][0] and rows[0][0]


def test_uploads_not_served_statically(client, data_dir):
    from conftest import image_files
    post_project(client, files=image_files())
    f = next((data_dir / "uploads").rglob("*.png"))
    for path in (f"/uploads/{f.name}", f"/data/uploads/{f.name}", f"/{f.name}"):
        assert client.get(path).status_code == 404 or "image" not in client.get(path).headers.get("content-type", "")


def test_api_route_precedes_static(client):
    r = client.get(f"{API}/projects")
    assert r.headers["content-type"].startswith("application/json")
