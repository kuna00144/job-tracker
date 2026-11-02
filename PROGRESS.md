# PROGRESS

## 완료
- 사람인 목록 페이지 구조 확인(공고ID = `div.list_item#rec-{ID}`, 마감 `.support_info .date`)
- 뼈대: `main.py`, `jobtracker/{saramin,notion,sync}.py`, 테스트(파서·마감일·403 중단)

## 다음 할 일
1. 노션: integration 토큰 발급, 수집함/지원현황 DB 생성(SPEC 스키마), 각 DB에 integration 연결, `.env` 작성
2. 사람인 이용약관에서 자동 수집 관련 조항 확인
3. `--job` 직군 코드 확장: 현재 `jobs.json`에는 확인된 `IT개발·데이터`(cat_mcls=2)만 있음. 백엔드 등 세부 직군(cat_kewd 등)은 URL 구조 확인 필요
4. `page_count=50`을 서버가 받아주는지 확인(안 받으면 10건씩 오고 페이지 루프로 처리됨, 100건 = 10회 요청 × 3초)
5. SPEC 완료 검증 항목을 실제 노션로 하나씩 확인 (노션 연동은 아직 실제 호출로 검증 안 됨)
