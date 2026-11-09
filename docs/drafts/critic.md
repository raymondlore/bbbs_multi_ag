# 비판적 검토 결과 (critic)

대상: docs/drafts/ux.md, docs/drafts/architect.md. 심각도 H/M/L.

## 1. 합의된 결정
1. 태그 필터는 단일 선택(리더 결정). 복수 AND는 2차. API `tag`도 1개로 단순화.
2. 경로 `/api/v1/projects`, 화면 문구 "과제"(리더 결정).
3. 수정/삭제 비밀번호는 저장·삭제 요청 시점에만 검증. `/verify` 엔드포인트 제거(범위 축소).
4. `GET /tags` 유지(칩 필터 소스), 사용 중인 태그만 반환.
5. 비밀번호는 서버 발급 12자리 무작위(secrets, 혼동문자 제외, 약 59bit), PBKDF2-SHA256 12만 회 + salt, hmac.compare_digest. 응답 1회 노출, 복구 수단 없음(운영자가 DB에서 처리).
6. 429 락아웃: 리더 방침 및 architect 안(프로젝트+IP 키, 연속 5회 실패 시 15분, Retry-After 900, 워커 1개, 메모리 dict+lock)을 수용. critic의 제외 권고는 이견으로 기록(아래 4-1). 한계(재시작 초기화, 다중 워커 무력, 타인이 소유자를 잠그는 DoS)를 plan에 명시.
7. 링크는 서버(urlparse: http/https + netloc, 제어문자 거부)와 클라이언트(new URL protocol 검사)에서 이중 검증, `rel="noopener noreferrer"`.
8. 업로드: 확장자+매직바이트, 읽는 도중 2MB+1B 중단, uuid 파일명, SVG 금지, 웹 루트 밖 저장, API 경유 제공(nosniff).
9. 오류: 422/404/405/500을 전부 `{"error":{code,message}}`로 통일, 스택 미노출. 비번은 헤더만(URL/해시에 금지), 비번 안내 화면은 JS 메모리만(새로고침 유실 명시, 체크박스 후 이동).
10. 폐쇄망: 외부 폰트/CDN/아이콘 없음, FastAPI `/docs`·`/redoc` 비활성화, clipboard API 실패(http) 시 읽기전용 입력 선택 폴백.

## 2. 반영 요청한 지적(architect/ux 문서에 반영 확인 필요)
- [M] 이미지 캐시: public max-age 1시간이면 교체 후 stale -> `?v=updated_at` 또는 no-cache/ETag. edit_password 응답은 `Cache-Control: no-store`.
- [M] 보안 헤더: CSP(default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'), nosniff. 인라인 script/onclick 금지. `/api` 라우터 등록 후 StaticFiles 마운트.
- [M] 파일/DB 순서: 새 파일 저장 -> DB 커밋 -> 이전 파일 삭제. 실패 시 새 파일 정리(고아 파일 방지).
- [M] 운영: DATA_DIR 환경변수, 연결마다 foreign_keys=ON·busy_timeout, WAL, 백업은 `sqlite3 .backup` + uploads 동시 보관, wheelhouse 오프라인 설치.
- [M] PBKDF2는 블로킹이므로 `def` 핸들러(스레드풀) 사용.
- [L] 목록 항목에 `has_image` 없음 -> ux는 `image_url` null 판정으로 대체. ux.md 문구 정정 필요.
- [L] 429 문구/Retry-After 처리는 락아웃 제외 시 ux.md에서 삭제.
- [L] 비번 입력란 type=password autocomplete=off, 삭제 다이얼로그 403 시 유지.
- [L] 상세 응답 스키마는 architect 3.3 기준(ux 미결 5 해소).

## 3. 범위 점검 결과
- 로그인/댓글/좋아요/관리자/조회수/다크모드/임시저장/마크다운: 두 초안 모두 미포함(양호).
- 범위 축소: `/verify`, 429 락아웃(제안), 복수 태그 AND. 과잉 방지: 썸네일 생성·FTS5·멱등키·PATCH·재발급 기능 모두 제외 동의.

## 4. 리더 최종 결정 (결정됨)
1. 429 락아웃 유지: 메모리 dict+lock 최소 구현, 키 (project_id, IP), 연속 5회 실패 시 15분, Retry-After 900, 워커 1개. 재시작 초기화·다중 워커 무력·12자리 무작위라 실효 낮음·타인이 잠그는 DoS 가능성을 plan에 기록. critic의 제외 권고는 이견으로만 남김(architect와 합의: 유지+한계 명시).
2. `python-multipart` 승인, requirements `==` 고정, wheelhouse 포함.
3. http 평문 비밀번호 전송은 MVP에서 수용, plan.md 위험 요소로 기록, HTTPS는 배포 단계 권고.

## 4-1. 추가 결정
- 검증 실패는 422 VALIDATION_ERROR로 통일(리더 결정, 400 아님). 배포·분석 URL 둘 다 비면 422. ux.md의 400 언급은 422로 정정 필요. 보안상 문제 없음.

## 5. 잔여 확인 사항
- architect.md B1,B3~B9 반영 확인됨(/verify 삭제, ?v=updated_at, no-store, CSP, 저장-커밋-삭제 순서, URL netloc 검증).
- ux.md의 `has_image` 문구는 `image_url` null 판정으로 정정되었는지 통합 시 확인.

## 6. 미결 쟁점
없음. (X-Forwarded-For 신뢰 여부는 배포 환경 확정 후 결정, architect §8-2)
