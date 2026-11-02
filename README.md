# job-tracker

개인 취업 준비용 도구입니다. 선택한 직군의 채용공고를 가져와 본인 노션에 정리합니다.
비상업적 개인 용도이며, 수집한 데이터는 외부에 공개·재배포하지 않고 이 저장소에도 포함하지 않습니다.

## 동작
- 노션 DB 두 개를 사용합니다. **수집함**(스크립트가 관리)과 **지원현황**(사용자가 관리).
- 수집함에서 `지원할래`를 체크하고 실행하면 지원현황으로 옮겨집니다.
- 마감일이 지난 수집함 공고는 정리됩니다.

## 수집 원칙
- 공고 목록 페이지만 요청하고 상세 페이지는 요청하지 않습니다.
- 요청 사이 3초 이상 대기하고, 실행할 때만 수집합니다.
- User-Agent를 위장하지 않으며, 차단(403/429/CAPTCHA)이 감지되면 우회하지 않고 즉시 중단합니다.
- 자세한 내용은 [DECISIONS.md](DECISIONS.md) 참고.

## 사용
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # 노션 토큰과 DB ID 입력
.venv/bin/python main.py --job "IT개발·데이터"
.venv/bin/python -m pytest
```

## 상태
개발 중. 진행 상황은 [PROGRESS.md](PROGRESS.md) 참고.
