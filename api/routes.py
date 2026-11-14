"""과제 API 라우터 (/api/v1)."""
import sqlite3
from datetime import datetime

from fastapi import APIRouter, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from . import lockout, security, storage
from .db import connect, now_iso
from .errors import ApiError
from .validation import ProjectInput, fail, validate_project

router = APIRouter(prefix="/api/v1")

PROJECT_COLUMNS = (
    "id, title, description, deploy_url, repo_url, author, image_filename, created_at, updated_at"
)


# ---------- 공통 헬퍼 ----------

def unix_seconds(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def image_url(row: sqlite3.Row) -> str | None:
    if not row["image_filename"]:
        return None
    return f"/api/v1/projects/{row['id']}/image?v={unix_seconds(row['updated_at'])}"


def get_tags(conn: sqlite3.Connection, project_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT t.name FROM project_tags pt JOIN tags t ON t.id = pt.tag_id "
        "WHERE pt.project_id = ? ORDER BY pt.rowid",
        (project_id,),
    ).fetchall()
    return [r["name"] for r in rows]


def project_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "deploy_url": row["deploy_url"],
        "repo_url": row["repo_url"],
        "author": row["author"],
        "tags": get_tags(conn, row["id"]),
        "image_url": image_url(row),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def fetch_project(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row:
    row = conn.execute(f"SELECT {PROJECT_COLUMNS} FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "과제를 찾을 수 없습니다.")
    return row


def replace_tags(conn: sqlite3.Connection, project_id: int, tags: list[str]) -> None:
    """과제의 태그를 전부 교체하고 사용되지 않는 태그를 정리한다."""
    conn.execute("DELETE FROM project_tags WHERE project_id = ?", (project_id,))
    for name in tags:
        conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,))
        tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()["id"]
        conn.execute("INSERT INTO project_tags(project_id, tag_id) VALUES (?, ?)", (project_id, tag_id))
    cleanup_orphan_tags(conn)


def cleanup_orphan_tags(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM project_tags)")


def authorize(request: Request, conn: sqlite3.Connection, project_id: int, password: str | None) -> sqlite3.Row:
    """존재 확인 → 헤더 확인 → 잠금 확인 → 해시 검증 순서로 처리한다."""
    fetch_project(conn, project_id)
    if password is None or not password.strip():
        raise ApiError(401, "PASSWORD_REQUIRED", "비밀번호를 입력하세요.")
    ip = lockout.get_client_ip(request)
    if lockout.locked_seconds(project_id, ip) > 0:
        raise ApiError(
            429, "TOO_MANY_ATTEMPTS", "시도 횟수를 초과했습니다. 잠시 후(약 15분) 다시 시도하세요.",
            {"Retry-After": str(lockout.LOCK_SECONDS)},
        )
    stored = conn.execute("SELECT password_hash FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not security.verify_password(password, stored["password_hash"]):
        lockout.record_failure(project_id, ip)
        raise ApiError(403, "PASSWORD_MISMATCH", "비밀번호가 일치하지 않습니다.")
    lockout.record_success(project_id, ip)
    return fetch_project(conn, project_id)


def parse_flag(value: str | None) -> bool:
    return (value or "").strip().lower() in ("true", "1")


# ---------- 등록 ----------

@router.post("/projects")
def create_project(
    title: str = Form(""),
    description: str = Form(""),
    author: str = Form(""),
    deploy_url: str = Form(""),
    repo_url: str = Form(""),
    tags: list[str] = Form(default=[]),
    image: UploadFile | None = File(None),
) -> JSONResponse:
    data = validate_project(title, description, author, deploy_url, repo_url, tags)
    upload = storage.read_image(image) if storage.has_upload(image) else None
    filename = storage.save_image(*upload) if upload else None
    password = security.generate_password()
    now = now_iso()
    try:
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO projects(title, description, deploy_url, repo_url, author, password_hash, "
                "image_filename, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (data.title, data.description, data.deploy_url, data.repo_url, data.author,
                 security.hash_password(password), filename, now, now),
            )
            project_id = int(cur.lastrowid)
            replace_tags(conn, project_id, data.tags)
            body = {"project": project_dict(conn, fetch_project(conn, project_id)), "edit_password": password}
    except Exception:
        storage.delete_image(filename)
        raise
    return JSONResponse(body, status_code=201, headers={"Cache-Control": "no-store"})


# ---------- 목록 ----------

def escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/projects")
def list_projects(
    page: int = Query(1, ge=1, le=1_000_000_000),
    page_size: int = Query(20, ge=1, le=50),
    q: str | None = Query(None),
    tag: str | None = Query(None),
) -> dict:
    keyword = (q or "").strip()
    if len(keyword) > 100:
        raise fail("q", "100자 이하로 입력하세요.")
    where: list[str] = []
    params: list[object] = []
    if keyword:
        like = f"%{escape_like(keyword)}%"
        where.append("(p.title LIKE ? ESCAPE '\\' OR p.description LIKE ? ESCAPE '\\')")
        params += [like, like]
    tag_name = (tag or "").strip()
    if tag_name:
        where.append(
            "EXISTS (SELECT 1 FROM project_tags pt JOIN tags t ON t.id = pt.tag_id "
            "WHERE pt.project_id = p.id AND t.name = ?)"
        )
        params.append(tag_name)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n FROM projects p {clause}", params).fetchone()["n"]
        rows = conn.execute(
            f"SELECT p.id, p.title, p.description, p.author, p.image_filename, p.created_at, p.updated_at "
            f"FROM projects p {clause} ORDER BY p.created_at DESC, p.id DESC LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
        items = [summary_dict(conn, row) for row in rows]
    return {"items": items, "page": page, "page_size": page_size, "total": total}


def summary_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    text = row["description"]
    summary = text if len(text) <= 150 else text[:150] + "..."
    return {
        "id": row["id"],
        "title": row["title"],
        "summary": summary,
        "author": row["author"],
        "tags": get_tags(conn, row["id"]),
        "image_url": image_url(row),
        "created_at": row["created_at"],
    }


# ---------- 상세 ----------

@router.get("/projects/{project_id}")
def get_project(project_id: int) -> dict:
    with connect() as conn:
        return project_dict(conn, fetch_project(conn, project_id))


# ---------- 수정 ----------

@router.put("/projects/{project_id}")
def update_project(
    project_id: int,
    request: Request,
    x_edit_password: str | None = Header(None),
    title: str = Form(""),
    description: str = Form(""),
    author: str = Form(""),
    deploy_url: str = Form(""),
    repo_url: str = Form(""),
    tags: list[str] = Form(default=[]),
    remove_image: str = Form(""),
    image: UploadFile | None = File(None),
) -> dict:
    with connect() as conn:
        old = authorize(request, conn, project_id, x_edit_password)
        data = validate_project(title, description, author, deploy_url, repo_url, tags)
        remove = parse_flag(remove_image)
        has_new = storage.has_upload(image)
        if has_new and remove:
            raise fail("remove_image", "image와 remove_image를 함께 보낼 수 없습니다.")
        upload = storage.read_image(image) if has_new else None
        new_name = storage.save_image(*upload) if upload else None
        try:
            body = apply_update(conn, old, data, new_name, remove)
        except Exception:
            storage.delete_image(new_name)
            raise
    if new_name or remove:
        storage.delete_image(old["image_filename"])  # 커밋 이후에 이전 파일 삭제
    return body


def apply_update(
    conn: sqlite3.Connection, old: sqlite3.Row, data: ProjectInput, new_name: str | None, remove: bool
) -> dict:
    filename = new_name if new_name else (None if remove else old["image_filename"])
    conn.execute(
        "UPDATE projects SET title = ?, description = ?, deploy_url = ?, repo_url = ?, author = ?, "
        "image_filename = ?, updated_at = ? WHERE id = ?",
        (data.title, data.description, data.deploy_url, data.repo_url, data.author,
         filename, now_iso(), old["id"]),
    )
    replace_tags(conn, old["id"], data.tags)
    return {"project": project_dict(conn, fetch_project(conn, old["id"]))}


# ---------- 삭제 ----------

@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int, request: Request, x_edit_password: str | None = Header(None)
) -> Response:
    with connect() as conn:
        row = authorize(request, conn, project_id, x_edit_password)
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        cleanup_orphan_tags(conn)
    storage.delete_image(row["image_filename"])
    return Response(status_code=204)


# ---------- 이미지 ----------

@router.get("/projects/{project_id}/image")
def get_image(project_id: int) -> FileResponse:
    with connect() as conn:
        row = fetch_project(conn, project_id)
    filename = row["image_filename"]
    path = storage.image_path(filename) if filename else None
    if path is None or not path.is_file():
        raise ApiError(404, "NOT_FOUND", "이미지를 찾을 수 없습니다.")
    media_type = storage.MEDIA_TYPES[path.suffix.lstrip(".")]
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "public, max-age=3600"})


# ---------- 태그 ----------

@router.get("/tags")
def list_tags() -> dict:
    with connect() as conn:
        rows = conn.execute(
            "SELECT t.name AS name, COUNT(*) AS count FROM tags t "
            "JOIN project_tags pt ON pt.tag_id = t.id GROUP BY t.id ORDER BY count DESC, t.name ASC"
        ).fetchall()
    return {"items": [{"name": r["name"], "count": r["count"]} for r in rows]}
