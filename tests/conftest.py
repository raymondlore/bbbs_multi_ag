"""공통 fixture. 계약서(docs/api.md)와 docs/tasks.md '팀 간 약속'의 이름만 사용한다."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

API = "/api/v1"

# 매직 바이트만 맞춘 최소 이미지 바이트
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF" + b"\x24\x00\x00\x00" + b"WEBP" + b"\x00" * 64


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("DATA_DIR", str(d))
    monkeypatch.delenv("TRUST_PROXY", raising=False)
    return d


@pytest.fixture
def client(data_dir):
    from api.main import app
    from api.lockout import reset_lockout

    reset_lockout()
    with TestClient(app) as c:
        yield c
    reset_lockout()


def base_form(**over):
    """등록 폼 기본값. 값이 None이면 해당 필드를 보내지 않는다."""
    form = {
        "title": "사내 규정 챗봇",
        "description": "규정 문서를 검색해 답하는 챗봇",
        "author": "홍길동",
        "deploy_url": "http://10.0.0.5:8080",
    }
    form.update(over)
    return {k: v for k, v in form.items() if v is not None}


def post_project(client, files=None, headers=None, **over):
    """tags는 리스트로 주면 같은 이름 필드를 반복한다."""
    data = base_form(**over)
    return client.post(f"{API}/projects", data=data, files=files, headers=headers)


def make_project(client, **over):
    """등록 후 (project, password) 반환. 실패하면 assert."""
    r = post_project(client, **over)
    assert r.status_code == 201, r.text
    body = r.json()
    return body["project"], body["edit_password"]


def pw(password):
    return {"X-Edit-Password": password}


def image_files(content=PNG, name="shot.png", ctype="image/png"):
    return {"image": (name, content, ctype)}
