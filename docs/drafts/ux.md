# UX 화면 흐름 (ux 최종안: architect/critic 반영)

전제: 순수 HTML/CSS/JS(ES Modules), 외부 CDN·폰트·아이콘 없음(시스템 폰트 스택, 아이콘은 인라인 SVG/유니코드), 사용자 입력은 textContent만, 해시 라우팅, 모바일/태블릿 반응형(단일 컬럼 -> 넓은 화면 카드 그리드). MVP 밖 요소(로그인/댓글/좋아요/관리자/조회수/다크모드/임시저장/마크다운) 제외. 설명은 `white-space: pre-wrap`로 줄바꿈만 처리.

## 1. 화면 흐름 (화면 3개 + 안내 1개, 수정은 등록 폼 재사용)
목록(`#/`) -> 등록(`#/new`) -> 비밀번호 안내 -> 상세(`#/projects/{id}`) -> 수정(`#/projects/{id}/edit`, 등록 폼 재사용) / 삭제(확인 다이얼로그)
목록 상태는 URL 보존: `#/?q=&tag=a&page=` (뒤로가기 가능, 값은 encodeURIComponent).

## 2. 화면별 구성
### 목록
- 상단: 제목, [과제 등록], 검색 입력(과제명·설명), 태그 칩 필터(GET /tags의 name+count, 단일 선택, 선택 칩 재클릭으로 해제; URL은 `tag=` 1개)
- 항목: 제목, summary(150자), 작성자, 태그 칩, 등록일, 썸네일(image_url이 null이 아니면 표시, null이면 인라인 SVG 대체)
- 페이지네이션 20개/페이지: 이전/다음 + 번호(최대 5개) + 총 건수. 검색/필터 변경 시 page=1로 초기화.
- 상태: 로딩 / 빈(과제 없음: 첫 등록 유도) / 빈(결과 없음: 필터 초기화) / 오류(메시지+재시도)
### 등록 / 수정 (같은 폼)
- 필드: 과제명*(<=100), 설명*(<=2000, 글자수 표시), 배포 URL / 저장소 URL(**둘 중 최소 1개 필수**, 각 <=500자, http/https만; 둘 다 비우면 제출 전 오류 "배포 URL 또는 저장소 URL 중 하나는 입력해야 합니다", 서버 422도 같은 위치에 표시), 작성자*(<=30), 태그(엔터/콤마로 칩 추가, 중복 제거, 각 <=20자, 최대 5개), 스크린샷(png/jpg/webp, 2MB, createObjectURL 미리보기, 제거)
- 클라이언트 사전검증은 편의용, 최종은 서버. 서버 422 VALIDATION_ERROR는 error.message를 폼 상단에 표시. 제출 중 버튼 비활성(이중 제출 방지).
- 413/415는 스크린샷 필드 옆 오류로 표시.
- 수정 모드: 기존값 프리필, 스크린샷 유지/교체/제거(remove_image), 수정용 비밀번호 입력란이 폼 하단에 있고 저장 시 X-Edit-Password로 전송. 사전 검증 엔드포인트 없음(합의안, 아래).
- 실패 시 입력값은 유지(비번 틀려도 폼 내용 보존).
### 비밀번호 안내 (등록 201 직후)
- edit_password 표시, [복사] 버튼(clipboard 실패 시 선택 가능한 텍스트로 대체), 경고: "다시 볼 수 없으며 분실 시 수정·삭제 불가(MVP)"
- "보관했습니다" 체크 후 [상세 보기] 활성화. 비밀번호는 JS 메모리에만 보관, URL/localStorage 저장 금지. 새로고침 시 유실 명시.
### 상세
- 전체 정보, 스크린샷(없으면 영역 숨김), 링크는 새 탭 `rel="noopener noreferrer"` (http/https만 href), [수정] [삭제] [목록으로]
- 상태: 로딩 / 404 NOT_FOUND(삭제되었거나 없음) / 오류
- 삭제: 확인 다이얼로그("되돌릴 수 없음") + 비밀번호 입력 -> DELETE. 성공 시 목록으로 이동 + 토스트.
### 비밀번호 오류 메시지
- 401 PASSWORD_REQUIRED: "비밀번호를 입력하세요" / 403 PASSWORD_MISMATCH: "비밀번호가 일치하지 않습니다"(재입력 허용) / 429 TOO_MANY_ATTEMPTS: "시도 횟수 초과, 잠시 후 다시 시도" (입력·버튼 일시 비활성) / 500: 일반 오류 문구.

## 3. 합의 사항 (architect 초안 기준)
1. 비밀번호는 서버 발급(12자리, 등록 응답에서 1회 노출). 사용자 지정 안 함.
2. 태그 필터는 단일 선택으로 확정(리더 결정). 복수 AND는 2차(API는 tag 반복 파라미터를 이미 지원하므로 화면만 확장).
3. 수정 비밀번호는 저장 시점에 입력(헤더). 별도 사전 검증 API 없음. 삭제도 다이얼로그에서 입력 후 즉시 DELETE.
4. 목록 응답은 `{items,page,page_size,total}`, 항목에 id,title,summary,author,tags,image_url,created_at 사용. 추가 필드 불필요.
5. 이미지는 multipart 단일 요청, 교체/제거는 PUT multipart(remove_image=true).
6. 오류 코드는 architect 목록(422/401/403/404/413/415/429/500)을 그대로 UI 문구에 매핑.
7. 화면은 목록/등록·수정(재사용)/상세로 최소화.

## 3-1. critic 지적 반영 (U1~U10)
- U1: 비번은 JS 메모리에만, URL/해시/sessionStorage 금지. 안내 화면 이탈 시 beforeunload 경고 + 체크박스 후 이동. 재발급 기능 없음.
- U3: href는 new URL() 파싱 후 protocol이 http:/https:일 때만 링크, 아니면 텍스트 표시. target=_blank rel="noopener noreferrer".
- U4: 403은 "비밀번호가 일치하지 않습니다"(남은 횟수 표시 없음), 429는 "잠시 후(약 15분) 다시 시도" + 입력 비활성. 서버 message는 textContent.
- U5: 이중 제출은 버튼 비활성 + "응답이 늦어도 다시 누르지 마세요" 안내만. 멱등키 없음.
- U6: URLSearchParams 파싱, page는 정수 검증(NaN/<1 -> 1). 상세에서 목록 복귀 시 필터 유지(뒤로가기/쿼리 보존).
- U7: createObjectURL 후 revoke, 이미지 대체는 인라인 SVG, alt는 과제명(textContent/alt 속성 설정).
- U9: 사내 http 배포라 navigator.clipboard 불가 가능. 복사 버튼은 실패 시 읽기전용 입력창 select() 폴백, 항상 선택 가능한 입력창으로 표시.
- U10: 수정 폼은 누구나 열 수 있고 비번은 저장/삭제 시에만 검증(합의 3과 동일).
- 기타: 인라인 script/onclick 금지(CSP 대비), ES Modules는 서버 서빙 전제.

## 3-2. critic 2차 (V1~V6) 반영
- V2: 비번 입력란 type=password, autocomplete=new-password. 안내 화면 비번은 읽기전용 input(select 가능).
- V3: 429에 Retry-After가 있으면 표시, 없으면 고정 문구. 입력 비활성은 편의일 뿐 서버가 최종.
- V4: 삭제 다이얼로그에서 403이면 다이얼로그 유지·재입력 허용.
- V1: 태그 칩은 전부 표시(상위 N개 제한 없음). 단일 선택 확정.
- 미결 3(저장 시점 비번)은 critic 동의로 해소.

## 3-3. 리더 결정 및 architect 최종안 반영
- 리더: 태그 필터 단일 선택, 경로 /api/v1/projects, 화면 문구 "과제" 통일(확정).
- architect 확정: 길이 제한 제목100/설명2000/작성자30/태그 20자x최대5개/URL 500자 http(s)만. 배포 URL / 저장소 URL 중 최소 1개 필수(리더 확정)(둘 다 비면 422). 폼에 "둘 중 하나 이상 입력" 안내와 클라이언트 사전검증, 상세에서 없는 링크 줄은 숨김.
- 목록 썸네일은 원본 이미지를 CSS로 축소(2MB 원본 로드 가능: loading="lazy" 사용).
- 목록 page_size 기본 20, 범위 밖 page는 200+빈 items -> "마지막 페이지로" 안내 또는 page=1 이동.
- 수정은 PUT 전체 교체: 프리필 값을 전부 전송(누락 시 비워짐). 수정 폼에서 URL/태그를 지우면 삭제됨.
- 경로 용어: 해시 라우트 `#/projects/{id}`, 화면 문구 "과제".
- architect가 제안한 POST /projects/{id}/verify: ux는 사용하지 않음(합의 3, critic도 불필요 판단). architect 쪽 제거 권고.
- 429(5회 실패 시 15분 잠금)는 architect 안에서 MVP 포함 여부 미정. 포함 시 UI 문구는 3-1 U4, 제외 시 해당 분기 삭제.

- architect 최종 확정: 429는 (과제,IP)별 연속 실패 5회 시 15분 잠금, Retry-After: 900 헤더 제공(MVP 포함) -> UI는 Retry-After를 분 단위로 환산해 표시. /verify 삭제, 수정 진입 무비번. GET /tags 유지. 상세 응답: id,title,description,deploy_url,repo_url,author,tags,image_url,created_at,updated_at.

## 4. 미결 쟁점
없음(ux 범위의 쟁점은 모두 합의됨).
