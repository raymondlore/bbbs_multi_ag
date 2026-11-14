import pytest
from conftest import API, JPG, PNG, WEBP, image_files, post_project

MB2 = 2 * 1024 * 1024


def err(r, status, code):
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code


def test_content_type_by_extension(client):
    for content, name, ctype, expect in [(PNG, "a.png", "image/png", "image/png"),
                                         (JPG, "a.jpg", "image/jpeg", "image/jpeg"),
                                         (WEBP, "a.webp", "image/webp", "image/webp")]:
        p = post_project(client, files=image_files(content, name, ctype)).json()["project"]
        r = client.get(f"/api/v1/projects/{p['id']}/image")
        assert r.status_code == 200
        assert r.headers["content-type"].split(";")[0] == expect
        assert r.content == content


def test_jpeg_extension_variant(client):
    r = post_project(client, files=image_files(JPG, "a.jpeg", "image/jpeg"))
    assert r.status_code == 201


def test_image_headers(client):
    p = post_project(client, files=image_files()).json()["project"]
    r = client.get(f"{API}/projects/{p['id']}/image")
    assert r.headers["cache-control"] == "public, max-age=3600"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_image_404_cases(client):
    p = post_project(client).json()["project"]  # 이미지 없음
    err(client.get(f"{API}/projects/{p['id']}/image"), 404, "NOT_FOUND")
    err(client.get(f"{API}/projects/9999/image"), 404, "NOT_FOUND")


def test_exactly_2mb_ok(client):
    data = PNG + b"\x00" * (MB2 - len(PNG))
    assert len(data) == MB2
    assert post_project(client, files=image_files(data)).status_code == 201


def test_over_2mb_413(client):
    data = PNG + b"\x00" * (MB2 - len(PNG) + 1)
    err(post_project(client, files=image_files(data)), 413, "IMAGE_TOO_LARGE")
    assert client.get(f"{API}/projects").json()["total"] == 0


@pytest.mark.parametrize("content,name,ctype", [
    (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "a.svg", "image/svg+xml"),
    (b"GIF89a" + b"\x00" * 20, "a.gif", "image/gif"),
    (b"hello", "a.txt", "text/plain"),
    (PNG, "a.exe", "image/png"),
    (PNG, "noext", "image/png"),
])
def test_unsupported_type_415(client, content, name, ctype):
    err(post_project(client, files=image_files(content, name, ctype)), 415, "IMAGE_TYPE_UNSUPPORTED")
    assert client.get(f"{API}/projects").json()["total"] == 0


@pytest.mark.parametrize("content,name", [
    (JPG, "a.png"), (PNG, "a.jpg"), (WEBP, "a.png"), (PNG, "a.webp"),
    (b"not an image at all", "a.png"),
    (b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 20, "a.webp"),
])
def test_magic_mismatch_415(client, content, name):
    err(post_project(client, files=image_files(content, name, "image/png")), 415, "IMAGE_TYPE_UNSUPPORTED")


def test_failed_upload_leaves_no_file(client, data_dir):
    post_project(client, files=image_files(b"nope", "a.png"))
    up = data_dir / "uploads"
    assert not up.exists() or [f for f in up.rglob("*") if f.is_file()] == []


def test_server_generated_filename(client, data_dir):
    post_project(client, files=image_files(PNG, "../../evil name.png"))
    files = [f for f in (data_dir / "uploads").rglob("*") if f.is_file()]
    assert len(files) == 1
    assert "evil" not in files[0].name and files[0].suffix == ".png"
    assert len(files[0].stem) == 32


@pytest.fixture(autouse=True)
def _fast(fast_hash):
    pass
