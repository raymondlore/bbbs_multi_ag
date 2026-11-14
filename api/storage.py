"""스크린샷 검증·저장·삭제. 저장 위치는 DATA_DIR/uploads (웹 루트 밖)."""
import uuid
from pathlib import Path

from fastapi import UploadFile

from .db import get_upload_dir
from .errors import ApiError

MAX_IMAGE_BYTES = 2_097_152
EXT_ALIASES = {"png": "png", "jpg": "jpg", "jpeg": "jpg", "webp": "webp"}
MEDIA_TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}


def _unsupported() -> ApiError:
    return ApiError(415, "IMAGE_TYPE_UNSUPPORTED", "png, jpg, webp 이미지만 올릴 수 있습니다.")


def _magic_matches(ext: str, data: bytes) -> bool:
    if ext == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == "jpg":
        return data.startswith(b"\xff\xd8\xff")
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def has_upload(image: UploadFile | None) -> bool:
    """파일이 실제로 첨부됐는지(빈 파일 파트는 미첨부로 본다)."""
    return image is not None and bool(image.filename)


def read_image(image: UploadFile) -> tuple[str, bytes]:
    """(정규화된 확장자, 바이트)를 반환한다. 2MB+1B까지만 읽는다."""
    name = (image.filename or "").lower()
    ext = EXT_ALIASES.get(name.rsplit(".", 1)[-1]) if "." in name else None
    if ext is None:
        raise _unsupported()
    data = image.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ApiError(413, "IMAGE_TOO_LARGE", "이미지는 2MB 이하여야 합니다.")
    if not _magic_matches(ext, data):
        raise _unsupported()
    return ext, data


def save_image(ext: str, data: bytes) -> str:
    """새 uuid 파일명으로 저장하고 파일명을 반환한다."""
    upload_dir = get_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    (upload_dir / filename).write_bytes(data)
    return filename


def delete_image(filename: str | None) -> None:
    if not filename:
        return
    try:
        (get_upload_dir() / Path(filename).name).unlink(missing_ok=True)
    except OSError:
        pass  # 파일 정리 실패는 요청 결과에 영향을 주지 않는다


def image_path(filename: str) -> Path:
    return get_upload_dir() / Path(filename).name
