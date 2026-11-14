"""입력 검증·정규화. 실패 시 ApiError(422)를 던진다."""
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from .errors import ApiError

TAG_PATTERN = re.compile(r"^[0-9A-Za-z가-힣ㄱ-ㆎ \-_.#+]+$")
MAX_TAGS = 5


@dataclass
class ProjectInput:
    title: str
    description: str
    author: str
    deploy_url: str | None
    repo_url: str | None
    tags: list[str]


def fail(field: str, reason: str) -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", f"{field}: {reason}")


def clean_text(value: str | None) -> str:
    return (value or "").strip()


def required_text(field: str, value: str | None, max_len: int) -> str:
    text = clean_text(value)
    if not text:
        raise fail(field, "필수 입력입니다.")
    if len(text) > max_len:
        raise fail(field, f"{max_len}자 이하로 입력하세요.")
    return text


def optional_url(field: str, value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if len(text) > 500:
        raise fail(field, "500자 이하로 입력하세요.")
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise fail(field, "공백이나 제어문자를 포함할 수 없습니다.")
    try:
        parsed = urlparse(text)
        valid = parsed.scheme in ("http", "https") and bool(parsed.netloc) and bool(parsed.hostname)
        parsed.port  # 잘못된 포트는 ValueError
    except ValueError:
        valid = False
    if not valid:
        raise fail(field, "http 또는 https 주소여야 합니다.")
    return text


def normalize_tags(raw_tags: list[str] | None) -> list[str]:
    """공백 정규화, 빈 항목 제거, 대소문자 무시 중복 제거 후 규칙을 검사한다."""
    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_tags or []:
        tag = " ".join((raw or "").split())
        if not tag:
            continue
        if len(tag) > 20:
            raise fail("tags", "각 태그는 20자 이하여야 합니다.")
        if not TAG_PATTERN.match(tag):
            raise fail("tags", "허용되지 않는 문자가 있습니다.")
        if tag.lower() not in seen:
            seen.add(tag.lower())
            result.append(tag)
    if len(result) > MAX_TAGS:
        raise fail("tags", f"태그는 최대 {MAX_TAGS}개입니다.")
    return result


def validate_project(
    title: str | None,
    description: str | None,
    author: str | None,
    deploy_url: str | None,
    repo_url: str | None,
    tags: list[str] | None,
) -> ProjectInput:
    data = ProjectInput(
        title=required_text("title", title, 100),
        description=required_text("description", description, 2000),
        author=required_text("author", author, 30),
        deploy_url=optional_url("deploy_url", deploy_url),
        repo_url=optional_url("repo_url", repo_url),
        tags=normalize_tags(tags),
    )
    if not data.deploy_url and not data.repo_url:
        raise fail("deploy_url", "deploy_url과 repo_url 중 하나 이상 필요합니다.")
    return data
