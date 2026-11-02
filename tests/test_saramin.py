from datetime import date

import pytest

from jobtracker import saramin
from jobtracker.saramin import BlockedError, fetch_postings, parse_deadline, parse_list

TODAY = date(2026, 11, 3)

# 실제 수집 데이터가 아니라 구조만 흉내 낸 손수 만든 조각
SNIPPET = """
<div id="rec-111" class="list_item"><div class="box_item">
  <div class="col company_nm"><a class="str_tit">테스트(주)</a></div>
  <div class="col notification_info"><div class="job_tit">
    <a class="str_tit" title="백엔드 개발자" href="/x"><span>백엔드 개발자</span></a></div></div>
  <div class="col recruit_info"><ul>
    <li><p class="work_place">서울 강남구</p></li><li><p class="career">신입</p></li></ul></div>
  <div class="col support_info"><p class="support_detail"><span class="date">~11.24(화)</span></p></div>
</div></div>
"""


def test_parse_list():
    [p] = parse_list(SNIPPET, TODAY)
    assert (p.posting_id, p.company, p.title, p.location, p.career) == ("111", "테스트(주)", "백엔드 개발자", "서울 강남구", "신입")
    assert p.deadline == date(2026, 11, 24) and p.deadline_kind == "날짜"
    assert "rec_idx=111" in p.url


@pytest.mark.parametrize(
    "text,expected",
    [
        ("D-5", (date(2026, 11, 8), "날짜")),
        ("~11.24(화)", (date(2026, 11, 24), "날짜")),
        ("~01.05(월)", (date(2027, 1, 5), "날짜")),
        ("상시채용", (None, "상시")),
        ("채용시", (None, "채용시")),
        ("오늘마감", (TODAY, "날짜")),
    ],
)
def test_parse_deadline(text, expected):
    assert parse_deadline(text, TODAY) == expected


class FakeResp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text
        self.ok = status < 400

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, *resps):
        self.resps, self.headers, self.calls = list(resps), {}, 0

    def get(self, *a, **k):
        self.calls += 1
        return self.resps.pop(0)


def test_403_stops_immediately_and_keeps_partial():
    s = FakeSession(FakeResp(200, SNIPPET), FakeResp(403))
    with pytest.raises(BlockedError) as ei:
        fetch_postings("2", 100, session=s, sleep=lambda _: None)
    assert s.calls == 2  # 재시도 없음
    assert [p.posting_id for p in ei.value.partial] == ["111"]


def test_captcha_detected():
    s = FakeSession(FakeResp(200, "<html>Please solve CAPTCHA</html>"))
    with pytest.raises(BlockedError):
        fetch_postings("2", 100, session=s, sleep=lambda _: None)


def test_zero_parsed_warns_not_deletes():
    s = FakeSession(FakeResp(200, "<html></html>"))
    postings, empty = fetch_postings("2", 100, session=s, sleep=lambda _: None)
    assert postings == [] and empty is True


def test_waits_between_pages():
    waits = []
    s = FakeSession(FakeResp(200, SNIPPET), FakeResp(200, ""))
    fetch_postings("2", 100, session=s, sleep=waits.append)
    assert waits == [saramin.MIN_DELAY_SEC]
