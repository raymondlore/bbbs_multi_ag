# DB·API 설계안 (architect)

상태: ux·critic 의견과 리더 결정(단일 태그 필터, 경로 `/projects`)을 반영한 최종안.

## 1. SQLite 스키마

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE projects (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  title         TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 100),
  description   TEXT NOT NULL CHECK (length(description) BETWEEN 1 AND 2000),
  deploy_url    TEXT,            -- http(s)만, 최대 500자 (deploy_url, repo_url 중 최소 1개 필수는 서버에서 검증)
  repo_url      TEXT,            -- http(s)만, 최대 500자
  author        TEXT NOT NULL CHECK (length(author) BETWEEN 1 AND 30),
  password_hash TEXT NOT NULL,   -- PBKDF2-HMAC-SHA256, "iterations$salt_hex$hash_hex"
  image_filename TEXT,           -- 서버 생성 파일명(uuid4hex.ext), 없으면 NULL
  created_at    TEXT NOT NULL,   -- ISO 8601 UTC, 예 2026-11-09T01:23:45Z
  updated_at    TEXT NOT NULL
);
CREATE INDEX idx_projects_created ON projects(created_at DESC, id DESC);

CREATE TABLE tags (
  id   INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK (length(name) BETWEEN 1 AND 20)
);

CREATE TABLE project_tags (
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (project_id, tag_id)
);
CREATE INDEX idx_project_tags_tag ON project_tags(tag_id, project_id);
```

- 태그: 과제당 최대 5개, 이름은 trim 후 공백 정규화, 대소문자 무시 중복 제거. 고아 태그는 삭제 시 정리(`DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM project_tags)`).
- 스크린샷: DB에는 파일명만, 파일은 `data/uploads/`(웹 루트 밖). 파일명은 서버가 `uuid4().hex + 확장자`로 생성. 원본 파일명은 저장하지 않음.
- 검색: `title LIKE ? ESCAPE '\' OR description LIKE ? ESCAPE '\'`(키워드의 `%`, `_`, `\` 이스케이프). FTS5는 MVP에서 제외(수천 건 규모에서 불필요, 한글 토크나이저 문제). 규모가 커지면 2차 검토.
- 태그 필터: 단일 `tag` 파라미터(리더 결정, 복수 AND는 2차). `EXISTS` 사용.
- 연결 설정: 요청마다 연결, 연결마다 `foreign_keys=ON`, `busy_timeout=5000`, WAL. DB/uploads 경로는 환경변수 `DATA_DIR`(기본 `./data`). 백업은 `sqlite3 .backup`과 `uploads/` 폴더를 함께 보관. uvicorn 워커는 1개로 고정(429 카운터 때문).
- 비밀번호: 서버가 12자리 랜덤(`secrets`, 혼동 문자 제외) 발급, PBKDF2-SHA256 12만 회 + 과제별 16바이트 salt. 비교는 `hmac.compare_digest`.

## 2. 공통 규칙
- 접두어 `/api/v1`, JSON snake_case, 날짜 ISO 8601 UTC.
- 오류: `{"error": {"code": "STRING_CODE", "message": "사람이 읽는 설명"}}`. FastAPI 기본 422 응답은 핸들러로 가로채 상태코드 422는 유지하되 본문을 `VALIDATION_ERROR` 형식으로 변환.
- 수정·삭제·검증의 비밀번호는 헤더 `X-Edit-Password`(URL·쿼리에 넣지 않음, 접근 로그 노출 방지).
- 등록/수정은 `multipart/form-data` 단일 요청(필드 + 선택 `image` 파일). `tags`는 쉼표 구분 문자열이 아니라 같은 이름의 `tags` 필드를 반복.

## 3. 엔드포인트

### 3.1 POST /api/v1/projects  — 과제 등록
요청(multipart): `title`*, `description`*, `author`*, `deploy_url`, `repo_url`, `tags`(반복, 0~5), `image`(선택)

응답 201:
```json
{
  "project": {
    "id": 12, "title": "사내 규정 챗봇", "description": "...", "deploy_url": "http://10.0.0.5:8080",
    "repo_url": null, "author": "홍길동", "tags": ["챗봇", "RAG"],
    "image_url": "/api/v1/projects/12/image?v=1794014625", "created_at": "2026-11-09T01:23:45Z", "updated_at": "2026-11-09T01:23:45Z"
  },
  "edit_password": "k7Xp2mQa9Tdw"
}
```
`edit_password`는 이 응답에서만 반환되고 이후 조회 불가. 이 응답에는 `Cache-Control: no-store`.

### 3.2 GET /api/v1/projects  — 목록
쿼리: `page`(기본 1, 최소 1), `page_size`(기본 20, 최대 50), `q`(과제명·설명, 최대 100자), `tag`(단일 값, 정확 일치·대소문자 무시).
정렬: `created_at DESC, id DESC` 고정.
응답 200:
```json
{
  "items": [
    {"id": 12, "title": "사내 규정 챗봇", "summary": "설명 앞 150자...", "author": "홍길동",
     "tags": ["챗봇", "RAG"], "image_url": "/api/v1/projects/12/image", "created_at": "2026-11-09T01:23:45Z"}
  ],
  "page": 1, "page_size": 20, "total": 37
}
```
`image_url`은 없으면 `null`(있으면 `/api/v1/projects/{id}/image?v=<updated_at>`). `has_image` 필드는 없으며 `image_url != null`로 판단. 범위를 벗어난 page는 200과 빈 `items`. 총 페이지 수는 클라이언트가 `ceil(total/page_size)`로 계산. 썸네일은 별도 생성하지 않고 원본 이미지를 CSS로 축소(MVP, Pillow 등 라이브러리 추가 회피).

### 3.3 GET /api/v1/projects/{id}  — 상세
응답 200: 3.1의 `project` 객체와 동일. 필드: `id, title, description`(전문), `deploy_url, repo_url, author, tags, image_url, created_at, updated_at`. 비밀번호 관련 필드(`password_hash` 포함)는 어떤 응답에도 없음. 없으면 404.

### 3.4 PUT /api/v1/projects/{id}  — 수정
헤더 `X-Edit-Password`. 요청(multipart): 등록과 동일 필드(전체 교체 방식; 누락된 `deploy_url`/`repo_url`/`tags`는 비움). 이미지: `image` 첨부 시 교체, `remove_image=true` 시 삭제, 둘 다 없으면 유지. 응답 200: `{"project": {...}}`.

### 3.5 DELETE /api/v1/projects/{id}  — 삭제
헤더 `X-Edit-Password`. 응답 204(본문 없음). 이미지 파일도 함께 삭제.

### 3.6 (삭제됨) 비밀번호 사전 확인 API
ux 합의: 수정 화면 진입은 비밀번호 없이 허용하고 저장·삭제 시점에만 입력. `/verify`는 두지 않음.

### 3.7 GET /api/v1/tags  — 태그 목록
응답 200: `{"items": [{"name": "챗봇", "count": 5}]}` 읽기 전용, 현재 사용 중인 태그만(JOIN 집계), 사용 횟수 내림차순, 이름 오름차순. 목록 화면의 태그 칩 필터 소스.

### 3.8 GET /api/v1/projects/{id}/image  — 스크린샷
이미지 바이너리. `Content-Type`은 저장 확장자로 결정, `X-Content-Type-Options: nosniff`, `Cache-Control: public, max-age=3600`(교체 시 stale 방지를 위해 `image_url`에 `?v=<updated_at 유닉스초>`를 붙임). 이미지가 없거나 과제가 없으면 404. (파일 경로를 직접 노출하지 않아 경로 조작 위험 없음.)

## 4. 입력 검증

| 필드 | 규칙 |
|---|---|
| title | 1~100자, trim |
| description | 1~2000자 |
| author | 1~30자 |
| deploy_url, repo_url | 선택, 최대 500자, `urlparse` 후 scheme이 `http`/`https`이고 netloc 존재, 공백·제어문자 거부 (`javascript:` 등 거부) |
| deploy_url / repo_url 조합 | 둘 중 최소 1개 필수 (둘 다 없으면 422 VALIDATION_ERROR) |
| tags | 0~5개, 허용 문자: 한글·영문·숫자·공백·`-_.#+`, 각 1~20자, 대소문자 무시 중복 제거 |
| image | png/jpg/webp(SVG 금지), 최대 2MB(2,097,152B). 확장자와 매직 바이트(PNG `89504E47`, JPEG `FFD8FF`, WEBP `RIFF....WEBP`) 둘 다 일치해야 함 |

## 5. 오류 코드

| HTTP | code | 상황 |
|---|---|---|
| 422 | VALIDATION_ERROR | 필드 검증 실패(message에 필드명 포함), 잘못된 page/page_size, deploy_url·repo_url 둘 다 비어 있음(리더 결정) |
| 401 | PASSWORD_REQUIRED | `X-Edit-Password` 헤더 없음 또는 빈 값 |
| 403 | PASSWORD_MISMATCH | 비밀번호 불일치 (403은 잠금이 아니라 불일치 전용) |
| 404 | NOT_FOUND | 과제 또는 이미지 없음 |
| 413 | IMAGE_TOO_LARGE | 이미지 2MB 초과 |
| 415 | IMAGE_TYPE_UNSUPPORTED | 형식 불허 또는 매직 바이트 불일치 |
| 405 | METHOD_NOT_ALLOWED | 허용되지 않은 메서드(전역 핸들러로 동일 형식) |
| 429 | TOO_MANY_ATTEMPTS | 비밀번호 실패 한도 초과. `Retry-After: 900` 헤더 |
| 500 | INTERNAL_ERROR | 서버 오류(내부 상세는 노출하지 않고 로그에만 기록) |

## 6. 보안·폐쇄망 메모
- 외부 의존 없음: 표준 `sqlite3`, `hashlib`, `secrets`, `hmac`만 사용. FastAPI 자동 문서(`/docs`)는 CDN에서 Swagger 리소스를 로드하므로 **폐쇄망에서는 비활성화**(`docs_url=None, redoc_url=None`)하고 계약서는 `docs/api.md`로 대체.
- 업로드 용량은 본문을 읽는 도중 2MB+1B에서 중단(전체를 메모리에 올리지 않음). multipart 파싱에는 `python-multipart` 필요(새 라이브러리, 리더 승인 필요).
- 모든 SQL은 파라미터 바인딩. 응답 JSON은 사용자 입력을 그대로 반환하며 이스케이프는 프런트의 `textContent`가 담당.
- 이미지는 웹 루트 밖에 저장하고 API 경유로만 제공.

### 비밀번호 시도 제한 (확정)
- 키 `(project_id, client_ip)`, 연속 실패 5회 시 15분(900초) 잠금, 성공하면 카운터 초기화. 프로세스 메모리 dict+lock 수십 줄. 재시작 시 초기화되며 워커 1개 전제.
- 프로젝트 단위 전체 잠금은 타인이 소유자를 막는 DoS가 되므로 쓰지 않음. 프록시 뒤라면 `X-Forwarded-For` 신뢰 여부를 배포 시 결정(기본은 직접 연결 IP).
- 존재하지 않는 id는 404, 비밀번호 해시 검증은 존재하는 과제에만 수행(MVP는 id가 순차 공개 정보라 존재 노출을 허용). 비밀번호 검증 핸들러는 `def`(스레드풀)로 작성해 PBKDF2가 이벤트 루프를 막지 않게 함. 비밀번호 알파벳은 혼동 문자(0O1lI) 제외 약 57자 x 12자리(약 70bit). 사용자 입력 비밀번호 필드는 API에 없음.
- 헤더 `X-Edit-Password`는 uvicorn 기본 로그에 남지 않으나 리버스 프록시 사용 시 헤더 로깅 금지를 배포 문서에 명시.

### 업로드·오류·헤더 (critic 반영)
- 저장 순서: 새 파일 저장 -> DB 커밋 -> 이전 파일 삭제(실패는 로그만). DB 실패 시 새 파일 삭제. 삭제는 DB 커밋 후 파일 삭제.
- 본문을 읽다 2MB+1B에서 중단해 413. DB 커밋 실패, 수정(교체), 삭제 시 이전/고아 파일을 삭제. 업로드 디렉터리는 StaticFiles로 마운트하지 않고 API로만 제공(목록 노출 없음).
- 전역 예외 핸들러: 422는 `VALIDATION_ERROR` 형식으로, 404/405/500도 `{"error":{...}}` 형식. 500은 일반 메시지만.
- 라우터 등록 순서: `/api` 라우터 먼저, 그다음 `StaticFiles(web, html=True)` 마운트.
- 보안 헤더(전 응답): `Content-Security-Policy: default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`. CORS는 동일 출처라 설정하지 않음(와일드카드 금지).
- 오프라인 설치: 의존성은 wheelhouse(`pip download -d wheelhouse` 후 `pip install --no-index --find-links`)로 반입.

## 7. ux 화면 요구와의 정렬
- 목록 응답 `items/page/page_size/total`, 태그 칩 소스 `GET /tags`, 단일 선택 `tag` 1개. 목록 썸네일은 원본 이미지(최대 2MB)를 CSS로 축소해 사용(MVP).
- 등록·수정은 multipart 단일 요청, 이미지 URL 필드는 `image_url`.
- 비밀번호는 헤더 전달, 저장·삭제 시점에만 입력(사전 확인 API 없음).
- 비밀번호 분실 복구 수단 없음으로 안내(MVP). 필요 시 운영자가 DB에서 직접 처리.

## 8. 미결 쟁점
1. **python-multipart**: 리더 승인 완료. `requirements.txt`에 `==`로 버전 고정(설치 가능한 최신 안정 버전을 리더가 확정), wheelhouse에 포함. plan에 기록.
1-1. **429 락아웃 (critic 이견)**: 리더 기본 방침은 유지. critic은 12자리 무작위 서버 발급이면 온라인 추측이 비현실적이라 MVP 제외를 권장. 최소 구현(메모리 dict+lock, 재시작 시 초기화, 워커 1개)으로 유지하되 최종 결정은 리더. 한계(재시작 초기화, 다중 워커 시 무력)는 plan에 기록.
2. **프록시 뒤 클라이언트 IP**: `X-Forwarded-For` 신뢰 여부는 배포 환경 확정 후 결정.
3. **썸네일**: 원본 사용. 목록 로딩 부담이 크면 2차에서 검토(Pillow는 추가 금지 기조).
4. **비밀번호 분실**: 복구 기능 없음, 운영자가 DB에서 직접 처리하는 절차를 운영 메모로. 관리자 화면은 2차.
5. **수정 방식**: PUT 전체 교체 채택.
