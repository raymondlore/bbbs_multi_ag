import pytest
from fastapi.testclient import TestClient
from conftest import API, base_form, make_project, pw


@pytest.fixture
def proxy_client(data_dir, monkeypatch):
    monkeypatch.setenv("TRUST_PROXY", "1")
    from api.main import app
    from api.lockout import reset_lockout
    reset_lockout()
    with TestClient(app) as c:
        yield c
    reset_lockout()


def wrong(client, pid, headers=None, method="delete"):
    h = {**pw("WRONGpassw0rd"), **(headers or {})}
    if method == "delete":
        return client.delete(f"{API}/projects/{pid}", headers=h)
    return client.put(f"{API}/projects/{pid}", data=base_form(), headers=h)


def lock(client, pid, headers=None):
    for i in range(5):
        r = wrong(client, pid, headers)
        assert r.status_code == 403, f"{i+1}번째 실패는 403이어야 함"


def test_locks_after_5_failures(client):
    p, _ = make_project(client)
    lock(client, p["id"])
    r = wrong(client, p["id"])
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    assert r.headers["retry-after"] == "900"


def test_correct_password_blocked_while_locked(client):
    p, password = make_project(client)
    lock(client, p["id"])
    r = client.delete(f"{API}/projects/{p['id']}", headers=pw(password))
    assert r.status_code == 429 and r.headers["retry-after"] == "900"
    r = client.put(f"{API}/projects/{p['id']}", data=base_form(title="x"), headers=pw(password))
    assert r.status_code == 429
    assert client.get(f"{API}/projects/{p['id']}").status_code == 200  # 삭제 안 됨


def test_put_failures_also_count(client):
    p, _ = make_project(client)
    for _ in range(5):
        assert wrong(client, p["id"], method="put").status_code == 403
    assert wrong(client, p["id"], method="put").status_code == 429
    assert wrong(client, p["id"], method="delete").status_code == 429  # 같은 (과제, IP) 카운터


def test_success_resets_counter(client):
    p, password = make_project(client)
    for _ in range(4):
        assert wrong(client, p["id"]).status_code == 403
    ok = client.put(f"{API}/projects/{p['id']}", data=base_form(), headers=pw(password))
    assert ok.status_code == 200
    for _ in range(4):
        assert wrong(client, p["id"]).status_code == 403  # 초기화됐으므로 다시 4회까지 403


def test_four_failures_not_locked(client):
    p, password = make_project(client)
    for _ in range(4):
        wrong(client, p["id"])
    assert client.put(f"{API}/projects/{p['id']}", data=base_form(), headers=pw(password)).status_code == 200


def test_lock_is_per_project(client):
    a, _ = make_project(client)
    b, pb = make_project(client)
    lock(client, a["id"])
    assert wrong(client, a["id"]).status_code == 429
    assert client.put(f"{API}/projects/{b['id']}", data=base_form(), headers=pw(pb)).status_code == 200


def test_missing_id_is_404_not_counted(client):
    for _ in range(10):
        assert wrong(client, 9999).status_code == 404


def test_missing_password_header_401(client):
    p, _ = make_project(client)
    for _ in range(3):
        assert client.delete(f"{API}/projects/{p['id']}").status_code == 401


def test_reset_lockout_function(client):
    from api.lockout import reset_lockout
    p, password = make_project(client)
    lock(client, p["id"])
    assert wrong(client, p["id"]).status_code == 429
    reset_lockout()
    assert client.delete(f"{API}/projects/{p['id']}", headers=pw(password)).status_code == 204


def test_xff_ignored_by_default(client):
    p, _ = make_project(client)
    for i in range(5):
        wrong(client, p["id"], {"X-Forwarded-For": f"1.2.3.{i}"})
    # 헤더를 바꿔도 같은 연결 IP이므로 잠김
    assert wrong(client, p["id"], {"X-Forwarded-For": "9.9.9.9"}).status_code == 429


def test_xff_used_when_trust_proxy(proxy_client):
    c = proxy_client
    p, password = make_project(c)
    lock(c, p["id"], {"X-Forwarded-For": "1.1.1.1"})
    assert wrong(c, p["id"], {"X-Forwarded-For": "1.1.1.1"}).status_code == 429
    # 다른 클라이언트 IP는 영향 없음
    assert wrong(c, p["id"], {"X-Forwarded-For": "2.2.2.2"}).status_code == 403
    ok = c.put(f"{API}/projects/{p['id']}", data=base_form(),
               headers={**pw(password), "X-Forwarded-For": "3.3.3.3"})
    assert ok.status_code == 200


# ---- 검사 순서: 404 -> 401 -> 429 -> 403 ----
def test_order_404_before_401(client):
    assert client.delete(f"{API}/projects/9999").status_code == 404


def test_order_401_before_429(client):
    p, _ = make_project(client)
    lock(client, p["id"])
    r = client.delete(f"{API}/projects/{p['id']}")  # 헤더 없음
    assert r.status_code == 401 and r.json()["error"]["code"] == "PASSWORD_REQUIRED"
    assert client.delete(f"{API}/projects/{p['id']}", headers=pw("")).status_code == 401


def test_order_429_before_403(client):
    p, _ = make_project(client)
    lock(client, p["id"])
    assert wrong(client, p["id"]).status_code == 429


def test_fifth_failure_is_403_sixth_is_429(client):
    p, _ = make_project(client)
    codes = [wrong(client, p["id"]).status_code for _ in range(6)]
    assert codes == [403] * 5 + [429]


def test_xff_first_value_used(proxy_client):
    c = proxy_client
    p, _ = make_project(c)
    lock(c, p["id"], {"X-Forwarded-For": "1.1.1.1, 10.0.0.1"})
    assert wrong(c, p["id"], {"X-Forwarded-For": "1.1.1.1, 10.9.9.9"}).status_code == 429  # 맨 앞 값이 같음
    assert wrong(c, p["id"], {"X-Forwarded-For": "2.2.2.2, 10.0.0.1"}).status_code == 403  # 맨 앞 값이 다름
