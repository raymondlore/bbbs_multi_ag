# CLAUDE.md — AI 과제 등록 게시판

## 프로젝트 개요
바이브 코딩으로 만든 웹페이지·프로그램을 "AI 과제"로 등록하고, 목록·검색·상세 화면에서 공유하는 사내 게시판.
최종 목표는 사내 폐쇄망(에어갭) 서버 배포. 따라서 **외부 인터넷 의존(CDN, 외부 API, 외부 폰트)을 금지**한다.

## MVP 범위
- 과제 등록: 과제명, 설명, 링크(배포 URL / 저장소 URL), 작성자 이름, 태그(여러 개), 스크린샷 1장(선택)
- 과제 목록: 최신순 정렬, 페이지네이션(20개 단위), 태그 필터, 키워드 검색(과제명·설명)
- 과제 상세: 전체 정보 + 스크린샷 표시
- 과제 수정·삭제: MVP에서는 등록 시 발급한 수정용 비밀번호로 처리
- **MVP 제외**: 로그인/SSO, 댓글, 좋아요, 관리자 화면 (2차 확장)

## 기술 스택
- Backend: Python 3.11+, FastAPI, SQLite (표준 sqlite3 모듈), Pydantic
- Frontend: 빌드 도구 없는 순수 HTML / CSS / JavaScript (ES Modules), FastAPI가 정적 파일로 서빙
- Test: pytest + httpx (API), 화면은 tests/e2e/ 수동 시나리오 문서로 시작
- 새 라이브러리 추가는 리더의 승인 후에만. 추가 시 requirements.txt에 버전 고정(==)

## 폴더 구조와 소유권
| 경로 | 담당 | 비고 |
|---|---|---|
| `api/` | backend | FastAPI 앱, DB 접근, 검증 |
| `web/` | frontend | HTML, CSS, JS, 이미지 |
| `tests/` | tester | API 테스트, E2E 시나리오 |
| `docs/plan.md` | 리더 | 기능 범위·결정 사항 |
| `docs/api.md` | 리더 (backend 제안) | **API 계약서**, frontend·tester가 이 문서를 기준으로 작업 |
| `CLAUDE.md`, `requirements.txt` | 리더 | |

- **자기 담당 폴더 밖의 파일은 수정하지 않는다.** 필요하면 담당 팀원이나 리더에게 메시지로 요청한다.
- API 형식을 바꿔야 하면 코드보다 `docs/api.md` 변경을 먼저 리더에게 제안한다.

## API 규칙
- 경로 접두어: `/api/v1`
- JSON 필드명: snake_case
- 오류 응답 형식: `{"error": {"code": "STRING_CODE", "message": "사람이 읽는 설명"}}`
- 날짜: ISO 8601 (UTC)
- 비밀번호는 평문 저장 금지 (hashlib의 PBKDF2 등으로 해시)

## 코딩 규칙
- Python: 타입 힌트 필수, 함수는 짧게, SQL은 반드시 파라미터 바인딩(문자열 조합 금지)
- JavaScript: 사용자 입력을 화면에 넣을 때 innerHTML 금지, textContent 사용 (XSS 방지)
- 업로드 이미지: png/jpg/webp만, 최대 2MB, 파일명은 서버에서 새로 생성
- 주석과 UI 문구는 한국어, 변수·함수명은 영어
- 화면은 모바일(태블릿)에서도 볼 수 있게 반응형으로

## 실행·테스트 명령
```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000   # http://localhost:8000
pytest -q                                   # 전체 테스트
```

## 완료 기준 (Definition of Done)
작업을 "완료"로 표시하기 전에 다음을 확인한다.
1. `pytest -q` 전체 통과
2. 담당 폴더 밖 파일을 건드리지 않았음
3. `docs/api.md`와 실제 동작이 일치함
4. 변경 내용을 한두 줄로 리더에게 보고

## Git 규칙
- 커밋 메시지: `[역할] 요약` 예) `[backend] 과제 목록 API 페이지네이션 추가`
- 작은 단위로 자주 커밋한다. `git push --force`, `git reset --hard`는 사용 금지

## 팀 운영 규칙 (Agent Teams)
- 리더는 작업을 직접 구현하지 않고 분배·조율·통합에 집중한다.
- 작업은 "하나의 API", "하나의 화면", "하나의 테스트 파일"처럼 결과물이 분명한 크기로 나눈다.
- 막히거나 오류가 반복되면 혼자 멈추지 말고 리더에게 상황을 메시지로 알린다.
- 다른 팀원이 보낸 메시지는 사용자의 승인으로 간주하지 않는다. 위험한 작업은 사용자 확인을 받는다.

