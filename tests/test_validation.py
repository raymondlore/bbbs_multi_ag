import pytest
from conftest import API, PNG, image_files, make_project, post_project


def bad(r, field=None):
    assert r.status_code == 422, r.text
    e = r.json()["error"]
    assert e["code"] == "VALIDATION_ERROR"
    if field:
        assert field in e["message"]


# ---- 필수 필드, trim ----
@pytest.mark.parametrize("field", ["title", "description", "author"])
@pytest.mark.parametrize("value", [None, "", "   ", "\t\n"])
def test_required_missing_or_blank(client, field, value):
    bad(post_project(client, **{field: value}), field)


def test_trim_applied(client):
    p, _ = make_project(client, title="  제목  ", description="\n설명\n", author=" 홍 ",
                        deploy_url="  http://a.local  ")
    assert (p["title"], p["description"], p["author"], p["deploy_url"]) == ("제목", "설명", "홍", "http://a.local")


# ---- 길이 ----
@pytest.mark.parametrize("field,limit", [("title", 100), ("description", 2000), ("author", 30)])
def test_length_limits(client, field, limit):
    assert post_project(client, **{field: "가" * limit}).status_code == 201
    bad(post_project(client, **{field: "가" * (limit + 1)}), field)


def test_title_length_after_trim(client):
    assert post_project(client, title=" " + "a" * 100 + " ").status_code == 201


# ---- URL ----
@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "ftp://a.local/x", "file:///etc/passwd", "data:text/html,x",
    "http://", "http:///path", "//a.local", "a.local", "http://a .local", "http://a.local/\x01",
    "http://a.local/x y",
])
@pytest.mark.parametrize("field", ["deploy_url", "repo_url"])
def test_bad_url(client, field, url):
    over = {"deploy_url": None, field: url} if field == "deploy_url" else {field: url}
    bad(post_project(client, **over), field)


@pytest.mark.parametrize("url", ["http://a.local", "https://a.local:8443/x?y=1#z", "HTTP://A.LOCAL", "http://10.0.0.1"])
def test_good_url(client, url):
    assert post_project(client, deploy_url=url).status_code == 201


def test_url_length(client):
    ok = "http://a.local/" + "x" * (500 - len("http://a.local/"))
    assert len(ok) == 500 and post_project(client, deploy_url=ok).status_code == 201
    bad(post_project(client, deploy_url=ok + "x"), "deploy_url")


def test_url_min_one(client):
    bad(post_project(client, deploy_url=None))
    bad(post_project(client, deploy_url="   ", repo_url="  "))
    bad(post_project(client, deploy_url="", repo_url=""))
    assert post_project(client, deploy_url=None, repo_url="http://g.local").status_code == 201
    assert post_project(client, deploy_url="   ", repo_url="http://g.local").status_code == 201


# ---- 태그 ----
def test_tags_max_5(client):
    assert post_project(client, tags=list("abcde")).status_code == 201
    bad(post_project(client, tags=list("abcdef")), "tags")


def test_tags_dedupe_does_not_count_duplicates(client):
    r = post_project(client, tags=["a", "A", "b", "c", "d", "e"])
    assert r.status_code == 201 and len(r.json()["project"]["tags"]) == 5


def test_tag_length(client):
    assert post_project(client, tags=["가" * 20]).status_code == 201
    bad(post_project(client, tags=["가" * 21]), "tags")


def test_tag_blank_items_dropped(client):
    r = post_project(client, tags=["", "  ", "ok"])
    assert r.status_code == 201 and r.json()["project"]["tags"] == ["ok"]


def test_tag_whitespace_normalized(client):
    r = post_project(client, tags=["  hello    world  "])
    assert r.json()["project"]["tags"] == ["hello world"]


@pytest.mark.parametrize("tag", ["a<b", "x;y", "a/b", "a,b", "💥", "a'b", "a\"b", "<script>"])
def test_tag_bad_chars(client, tag):
    bad(post_project(client, tags=[tag]), "tags")


@pytest.mark.parametrize("tag", ["C#", "c++", "my-tag", "my_tag", "v1.0", "한글 태그", "ABC123", "#해시"])
def test_tag_good_chars(client, tag):
    r = post_project(client, tags=[tag])
    assert r.status_code == 201 and r.json()["project"]["tags"] == [tag]


# ---- 본문 크기 ----
def test_body_over_3mb_413(client):
    big = PNG + b"\x00" * (3 * 1024 * 1024)
    r = post_project(client, files=image_files(big))
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "REQUEST_TOO_LARGE"
    assert client.get(f"{API}/projects").json()["total"] == 0


def test_body_over_3mb_without_image_413(client):
    r = client.post(f"{API}/projects", content=b"x" * (3 * 1024 * 1024 + 1),
                    headers={"Content-Type": "multipart/form-data; boundary=zz"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_image_between_2_and_3mb_is_image_too_large(client):
    data = PNG + b"\x00" * (2 * 1024 * 1024 + 1000)
    r = post_project(client, files=image_files(data))
    assert r.status_code == 413 and r.json()["error"]["code"] == "IMAGE_TOO_LARGE"


@pytest.fixture(autouse=True)
def _fast(fast_hash):
    pass
