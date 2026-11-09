# bbbs_multi_ag

AI 과제 등록 게시판 MVP의 계획 문서 저장소입니다. ux, architect, critic 세 에이전트의 토론 결과를 리더가 통합했습니다. 아직 코드는 없습니다.

- 사이트: https://raymondlore.github.io/bbbs_multi_ag/
- `docs/plan.md`: 기능 범위, 화면 흐름, 결정 사항
- `docs/api.md`: API 계약서
- `docs/drafts/`: 팀원별 초안과 검토 의견
- `CLAUDE.md`: 프로젝트 규칙

## 사이트 빌드
`main`에 push하면 GitHub Actions가 `scripts/build_site.py`로 `docs/`의 마크다운을 정적 HTML로 바꿔 GitHub Pages에 배포합니다. 로컬 확인:

```bash
pip install -r requirements-site.txt
python scripts/build_site.py   # _site/ 생성
```
