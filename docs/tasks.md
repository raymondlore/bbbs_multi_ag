# 구현 작업 목록 (task list)

리더가 관리한다. 팀원은 자기 작업을 끝내면 이 파일에서 **자기 줄의 체크박스만** `[x]`로 바꾸고(다른 줄·다른 내용은 수정 금지), 리더에게 한 줄로 보고한다. 막히면 상태를 `[!]`로 바꾸고 이유를 한 줄 덧붙인 뒤 리더에게 메시지를 보낸다.
기준 문서: `docs/api.md`(계약서, 고정), `docs/plan.md`(범위·결정), `CLAUDE.md`(규칙). 화면 세부는 `docs/drafts/ux.md`를 참고하되 충돌하면 `plan.md`·`api.md`가 우선한다.

## 팀 간 약속 (인터페이스)
tester는 backend보다 먼저 테스트를 쓰므로 아래 이름을 그대로 쓴다. 바꿔야 하면 리더에게 제안한다.
- 앱 진입점: `api/main.py`의 `app` (`uvicorn api.main:app --workers 1`)
- 데이터 경로: 환경변수 `DATA_DIR`(기본 `./data`). DB는 `$DATA_DIR/app.db`, 이미지는 `$DATA_DIR/uploads/`. `DATA_DIR`은 앱 시작(또는 첫 요청) 시점에 읽어서, 테스트가 임시 폴더로 바꿀 수 있어야 한다.
- 락아웃 초기화 함수: `api/lockout.py`의 `reset_lockout()` (HTTP 엔드포인트 아님)
- 프록시 신뢰: 환경변수 `TRUST_PROXY`(`1`이면 `X-Forwarded-For` 사용, 기본 불신)
- 정적 웹: `web/`을 `api/main.py`가 `/api` 라우터 등록 뒤에 `StaticFiles(web, html=True)`로 마운트
- Python 실행: 프로젝트 루트의 `.venv`(Python 3.12)를 쓴다. `source .venv/bin/activate` 후 `pytest -q`, `uvicorn ...`
- 커밋: `[역할] 요약`, 자기 폴더 파일만 `git add`, push 금지, `git push --force`·`git reset --hard` 금지

## backend (`api/`만)
- [x] B1 DB 스키마와 연결 (`api/db.py`): 테이블 3개, 인덱스, 연결마다 PRAGMA, 초기화 함수
- [x] B2 비밀번호 (`api/security.py`): 12자리 발급(혼동 문자 제외), PBKDF2 해시·검증(`hmac.compare_digest`)
- [x] B3 락아웃과 클라이언트 IP (`api/lockout.py`): (과제 id, IP) 5회/15분, 잠금 우선, `reset_lockout()`, `TRUST_PROXY`
- [x] B4 입력 검증·정규화 (`api/validation.py`): trim, 길이, URL 스킴, 태그 규칙, URL 최소 1개
- [x] B5 이미지 저장·삭제 (`api/storage.py`): 확장자+매직 바이트, 2MB 스트림 중단, uuid 파일명, 저장 순서
- [x] B6 앱 골격 (`api/main.py`): 전역 오류 핸들러(422→VALIDATION_ERROR 등), 보안 헤더, `/docs` 비활성, 본문 3MB `Content-Length` 검사(413 REQUEST_TOO_LARGE), StaticFiles 마운트 순서
- [x] B7 `POST /api/v1/projects` (등록, `edit_password` 1회 반환, `Cache-Control: no-store`)
- [x] B8 `GET /api/v1/projects` (목록: 페이지네이션, `q`, `tag`, 정렬, summary 150자)
- [x] B9 `GET /api/v1/projects/{id}` (상세)
- [x] B10 `PUT /api/v1/projects/{id}` (전체 교체, `remove_image`, image+remove_image 충돌 422)
- [x] B11 `DELETE /api/v1/projects/{id}` (204, 이미지 파일 삭제, 고아 태그 정리)
- [x] B12 `GET /api/v1/projects/{id}/image`
- [x] B13 `GET /api/v1/tags`
- [x] B14 `uvicorn api.main:app --workers 1` 실행 확인, `curl`로 등록→조회 스모크 테스트, 결과 보고

## frontend (`web/`만)
- [x] F1 앱 골격: `web/index.html`, 외부 CSS(`web/css/app.css`, 인라인 style·`<style>` 금지), ES Modules 구조, 해시 라우터, API 클라이언트(`web/js/api.js`), 공통 오류·토스트
- [x] F2 목록 화면: 카드 목록, 썸네일(없으면 SVG 대체), 로딩·빈·오류 상태
- [x] F3 목록의 검색·태그 칩 필터(단일)·페이지네이션, URL 상태 보존
- [x] F4 등록 폼: 필드, 태그 칩 입력, 스크린샷 미리보기, 클라이언트 검증(편의용), 서버 오류 표시
- [x] F5 비밀번호 안내 화면: 1회 표시, 복사 폴백, 보관 확인 체크
- [x] F6 상세 화면: 전체 정보, 스크린샷, 링크 http/https만, 404 상태
- [x] F7 수정 화면: 등록 폼 재사용, 프리필, 이미지 유지/교체/제거, 비밀번호 입력, 401/403/429 문구
- [x] F8 삭제 다이얼로그: 비밀번호 입력, 403 재입력, 성공 시 목록 이동
- [x] F9 반응형(모바일·태블릿)과 키보드 포커스 점검, innerHTML·인라인 스타일·외부 URL 없음 확인

## tester (`tests/`만)
- [x] T1 `tests/conftest.py`: 임시 `DATA_DIR`, 앱 import(`sys.path` 처리 포함), TestClient(httpx), 락아웃 초기화 fixture, 과제 생성 헬퍼
- [x] T2 `tests/test_projects_create.py`: 정상 201, `edit_password` 형식, 이미지 포함 등록
- [x] T3 `tests/test_projects_list.py`: 페이지네이션, 정렬, `q`, `tag`, 범위 밖 page
- [x] T4 `tests/test_projects_detail.py`: 상세 필드, 404, 비밀번호 필드 미노출
- [x] T5 `tests/test_projects_update.py`: 전체 교체, 이미지 교체·제거, image+remove_image 422, 401/403
- [x] T6 `tests/test_projects_delete.py`: 204, 이미지 삭제, 401/403/404
- [x] T7 `tests/test_image.py`: 형식·매직 바이트·2MB(413 IMAGE_TOO_LARGE, 415), 이미지 응답 헤더
- [x] T8 `tests/test_tags.py`: 사용 중 태그만, count, 정렬
- [x] T9 `tests/test_validation.py`: trim·빈 문자열, 길이, URL 스킴, URL 최소 1개, 태그 규칙, 본문 3MB(413 REQUEST_TOO_LARGE)
- [x] T10 `tests/test_lockout.py`: 5회 실패 후 429+`Retry-After`, 잠금 중 정답도 429, `TRUST_PROXY` 동작
- [x] T11 `tests/test_security.py`: 오류 형식, 보안 헤더, `/docs` 비활성, SQL 인젝션 문자열, 응답에 해시 미노출
- [x] T12 E2E 수동 시나리오 문서 `tests/e2e/` (목록·검색·필터 / 등록·비밀번호 안내 / 상세 / 수정·삭제 / 오류·잠금 각 1개 파일)
- [ ] T13 backend 완료 후 `pytest -q` 전체 실행, 실패 분석(api.md 기준으로 backend 버그인지 테스트 오류인지) 보고
