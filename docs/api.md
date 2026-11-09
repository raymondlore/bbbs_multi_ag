# API 계약서 (AI 과제 등록 게시판 MVP)

frontend·tester는 이 문서를 기준으로 작업한다. 변경이 필요하면 코드보다 이 문서의 변경을 먼저 리더에게 제안한다.

## 1. 공통 규칙
- 접두어 `/api/v1`, JSON 필드명 snake_case, 날짜는 ISO 8601 UTC(예: `2026-11-09T01:23:45Z`).
- 오류 응답 형식: `{"error": {"code": "STRING_CODE", "message": "사람이 읽는 설명"}}`
  - FastAPI 기본 422는 상태 코드를 유지하되 본문을 `VALIDATION_ERROR` 형식으로 변환하고, 404/405/500도 같은 형식을 쓴다. 500은 일반 메시지만 반환하고 상세는 로그에만 남긴다.
- 수정·삭제 비밀번호는 헤더 `X-Edit-Password`로만 전달한다(URL·쿼리 금지).
- 등록·수정은 `multipart/form-data` 단일 요청이다. `tags`는 같은 이름의 필드를 반복한다(쉼표 구분 문자열 아님).
- 이 API에는 사용자 지정 비밀번호 입력이 없다. 비밀번호는 서버가 발급한다.
- 모든 응답에 `X-Content-Type-Options: nosniff`와 `Content-Security-Policy: default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'`을 붙인다.

## 2. 엔드포인트 요약
| 메서드 | 경로 | 설명 | 비밀번호 |
|---|---|---|---|
| POST | `/api/v1/projects` | 과제 등록 | - |
| GET | `/api/v1/projects` | 목록(검색·태그 필터·페이지네이션) | - |
| GET | `/api/v1/projects/{id}` | 상세 | - |
| PUT | `/api/v1/projects/{id}` | 수정(전체 교체) | 필요 |
| DELETE | `/api/v1/projects/{id}` | 삭제 | 필요 |
| GET | `/api/v1/projects/{id}/image` | 스크린샷 | - |
| GET | `/api/v1/tags` | 사용 중인 태그 목록 | - |

비밀번호 사전 확인 엔드포인트(`/verify`)는 두지 않는다. 수정 화면은 비밀번호 없이 열 수 있고, 저장·삭제 시점에만 검증한다.

## 3. 엔드포인트 상세

### 3.1 POST /api/v1/projects — 과제 등록
요청(multipart): `title`*, `description`*, `author`*, `deploy_url`, `repo_url`, `tags`(반복, 0~5개), `image`(선택)
`deploy_url`과 `repo_url` 중 최소 1개는 필수다.

응답 201:
```json
{
  "project": {
    "id": 12,
    "title": "사내 규정 챗봇",
    "description": "규정 문서를 검색해 답하는 챗봇",
    "deploy_url": "http://10.0.0.5:8080",
    "repo_url": null,
    "author": "홍길동",
    "tags": ["챗봇", "RAG"],
    "image_url": "/api/v1/projects/12/image?v=1794014625",
    "created_at": "2026-11-09T01:23:45Z",
    "updated_at": "2026-11-09T01:23:45Z"
  },
  "edit_password": "k7Xp2mQa9Tdw"
}
```
- `edit_password`는 이 응답에서만 반환되며 이후 조회할 수 없다. 이 응답에는 `Cache-Control: no-store`를 붙인다.
- 이미지가 없으면 `image_url`은 `null`이다.

### 3.2 GET /api/v1/projects — 목록
쿼리:
| 이름 | 기본값 | 규칙 |
|---|---|---|
| `page` | 1 | 1 이상 정수 |
| `page_size` | 20 | 최대 50 |
| `q` | - | 과제명·설명 부분 일치, 최대 100자 |
| `tag` | - | 단일 값, 정확 일치(대소문자 무시) |

정렬은 `created_at DESC, id DESC`로 고정한다.

응답 200:
```json
{
  "items": [
    {
      "id": 12,
      "title": "사내 규정 챗봇",
      "summary": "설명 앞 150자...",
      "author": "홍길동",
      "tags": ["챗봇", "RAG"],
      "image_url": "/api/v1/projects/12/image?v=1794014625",
      "created_at": "2026-11-09T01:23:45Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 37
}
```
- `has_image` 필드는 없다. `image_url`이 `null`인지로 판단한다.
- 범위를 벗어난 `page`는 200과 빈 `items`를 반환한다. 총 페이지 수는 클라이언트가 `ceil(total/page_size)`로 계산한다.
- 썸네일은 별도로 만들지 않고 원본을 CSS로 축소한다.

### 3.3 GET /api/v1/projects/{id} — 상세
응답 200: 3.1의 `project` 객체와 같다(`id, title, description, deploy_url, repo_url, author, tags, image_url, created_at, updated_at`). 비밀번호 관련 필드는 어떤 응답에도 없다. 없으면 404.

### 3.4 PUT /api/v1/projects/{id} — 수정
헤더 `X-Edit-Password` 필요. 요청은 등록과 같은 필드이며 **전체 교체** 방식이다. 누락된 `deploy_url`, `repo_url`, `tags`는 비워진다.
- 이미지: `image`를 첨부하면 교체, `remove_image=true`면 삭제, 둘 다 없으면 유지.
- `image`와 `remove_image=true`가 함께 오면 422 `VALIDATION_ERROR`(이미지는 건드리지 않음).
- 잠금 상태이면 비밀번호가 맞아도 429를 반환한다(6절).
- 응답 200: `{"project": {...}}`

### 3.5 DELETE /api/v1/projects/{id} — 삭제
헤더 `X-Edit-Password` 필요. 응답 204(본문 없음). 이미지 파일도 함께 삭제한다. 잠금 상태이면 비밀번호가 맞아도 429를 반환한다(6절).

### 3.6 GET /api/v1/tags — 태그 목록
응답 200:
```json
{"items": [{"name": "챗봇", "count": 5}, {"name": "RAG", "count": 3}]}
```
현재 사용 중인 태그만 반환한다. 사용 횟수 내림차순, 이름 오름차순이다. 목록 화면의 태그 칩 필터 소스다.

### 3.7 GET /api/v1/projects/{id}/image — 스크린샷
이미지 바이너리를 반환한다. `Content-Type`은 저장 확장자로 정하고, `Cache-Control: public, max-age=3600`을 쓴다. 교체 시 오래된 이미지가 남지 않도록 `image_url`에 `?v=<updated_at 유닉스초>`를 붙인다. 이미지나 과제가 없으면 404.

## 4. 입력 검증
| 필드 | 규칙 |
|---|---|
| title | 1~100자, trim |
| description | 1~2000자 |
| author | 1~30자 |
| deploy_url, repo_url | 선택, 최대 500자, scheme이 `http`/`https`이고 netloc 존재, 공백·제어문자 거부(`javascript:` 등 거부) |
| URL 조합 | 둘 중 최소 1개 필수. 둘 다 없으면 422 VALIDATION_ERROR |
| tags | 0~5개, 각 1~20자, 허용 문자는 한글·영문·숫자·공백·`-_.#+`, trim·공백 정규화, 대소문자 무시 중복 제거 |
| image | png/jpg/webp만(SVG 금지), 최대 2MB(2,097,152B), 확장자와 매직 바이트가 모두 일치해야 함 |

**공통 입력 처리**
- 모든 텍스트 필드(`title`, `description`, `author`, `deploy_url`, `repo_url`)와 `tags`의 각 항목은 앞뒤 공백을 trim한 뒤 빈 문자열이면 미입력으로 간주한다. 필수 필드가 미입력이면 422, 선택 필드(URL)는 값이 없는 것으로 처리하며(그래서 URL 두 개가 모두 공백이면 "둘 다 없음" 규칙으로 422), 빈 `tags` 항목은 버린다.
- 요청 본문 전체가 3MB(3,145,728B)를 넘으면 413 `REQUEST_TOO_LARGE`를 반환한다. `Content-Length` 헤더 값으로 본문을 읽기 전에 판정한다. 이미지 한 장이 2MB를 넘는 경우의 `IMAGE_TOO_LARGE`와는 별개다.
- `image`와 `remove_image=true`는 함께 보낼 수 없다(PUT, 3.4절).

## 5. 오류 코드
| HTTP | code | 상황 |
|---|---|---|
| 422 | VALIDATION_ERROR | 필드 검증 실패(message에 필드명 포함), 잘못된 page/page_size, 배포·저장소 URL이 둘 다 비어 있음 |
| 401 | PASSWORD_REQUIRED | `X-Edit-Password` 헤더가 없거나 빈 값 |
| 403 | PASSWORD_MISMATCH | 비밀번호 불일치(잠금이 아니라 불일치 전용) |
| 404 | NOT_FOUND | 과제 또는 이미지 없음 |
| 405 | METHOD_NOT_ALLOWED | 허용되지 않은 메서드 |
| 413 | IMAGE_TOO_LARGE | 이미지 2MB 초과 |
| 413 | REQUEST_TOO_LARGE | 요청 본문 전체가 3MB 초과(`Content-Length` 기준) |
| 415 | IMAGE_TYPE_UNSUPPORTED | 형식 불허 또는 매직 바이트 불일치 |
| 429 | TOO_MANY_ATTEMPTS | 잠금 상태(비밀번호가 맞아도 동일). `Retry-After: 900` 헤더 |
| 500 | INTERNAL_ERROR | 서버 오류(상세는 로그에만) |

오류 응답 예시:
```json
{"error": {"code": "PASSWORD_MISMATCH", "message": "비밀번호가 일치하지 않습니다."}}
```

## 6. 비밀번호 정책
- 서버가 12자리 무작위(`secrets`, 혼동 문자 `0O1lI` 제외, 약 57자 알파벳, 약 70bit)로 발급하고, 사용자가 지정하지 않는다.
- PBKDF2-HMAC-SHA256 12만 회와 과제별 16바이트 salt로 저장하고, 비교는 `hmac.compare_digest`로 한다.
- 시도 제한: `(과제 id, 클라이언트 IP)`별로 연속 실패 5회면 15분 잠금하고, 성공하면 카운터를 초기화한다. 프로세스 메모리에 둔 카운터라 재시작하면 초기화되고, uvicorn 워커를 1개로 고정해야 한다.
- **잠금 확인이 먼저다.** 잠금 상태이면 비밀번호 해시 검증을 하지 않고, 정답 여부와 관계없이 429를 반환한다. 잠금 중의 요청은 실패 횟수에 더하지 않는다.
- 존재하지 않는 id는 404를 반환하고, 해시 검증은 존재하는 과제에만 수행한다.
- **클라이언트 IP:** 기본은 연결 IP(소켓의 peer 주소)를 쓰고 `X-Forwarded-For`는 신뢰하지 않는다. 환경변수 `TRUST_PROXY=1`일 때만 `X-Forwarded-For`를 사용한다(신뢰할 프록시 뒤에서만 켠다).
- **테스트용 초기화(tester 메모):** 락아웃 카운터를 비우는 함수(예: `reset_lockout()`)를 `api/` 코드에 두고, tester가 테스트마다(pytest fixture) 호출해 초기화한다. 이 함수는 HTTP 엔드포인트로 노출하지 않는다.
