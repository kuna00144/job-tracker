"""사람인 목록 페이지 수집.

규칙 (DECISIONS.md 참고):
- 목록 페이지(/zf_user/jobs/list/job-category)만 요청한다. 상세 페이지는 요청하지 않는다.
- 요청 사이 최소 3초 대기.
- 403/429/CAPTCHA 감지 시 재시도·우회 없이 BlockedError로 즉시 중단.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

import requests
from bs4 import BeautifulSoup

LIST_URL = "https://www.saramin.co.kr/zf_user/jobs/list/job-category"
BASE_URL = "https://www.saramin.co.kr"
MIN_DELAY_SEC = 3.0
PAGE_COUNT = 50  # 한 페이지 공고 수. 서버가 무시하면 10건씩 오므로 페이지 루프로 보충된다.


class BlockedError(Exception):
    """차단/CAPTCHA 감지. 재시도하지 않고 중단한다."""

    partial: list = []


@dataclass
class Posting:
    posting_id: str
    title: str
    company: str
    url: str
    deadline: date | None
    deadline_kind: str  # 날짜 / 상시 / 채용시
    location: str
    career: str


def parse_deadline(text: str, today: date | None = None) -> tuple[date | None, str]:
    today = today or date.today()
    text = text.strip()
    if "상시" in text:
        return None, "상시"
    if "채용시" in text:
        return None, "채용시"
    if "오늘마감" in text:
        return today, "날짜"
    m = re.fullmatch(r"D-(\d+)", text)
    if m:
        return today + timedelta(days=int(m.group(1))), "날짜"
    m = re.match(r"~?\s*(\d{1,2})\.(\d{1,2})", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        d = date(today.year, month, day)
        # 연말에 다음 해 1월 마감 공고를 볼 때를 보정 (6개월 넘게 과거면 내년으로 본다)
        if (today - d).days > 180:
            d = date(today.year + 1, month, day)
        return d, "날짜"
    return None, "채용시"


def parse_list(html: str, today: date | None = None) -> list[Posting]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Posting] = []
    for item in soup.select("div.list_item[id^=rec-]"):
        pid = item["id"].removeprefix("rec-")
        title_a = item.select_one(".job_tit a")
        company_a = item.select_one(".company_nm a.str_tit") or item.select_one(".company_nm")
        if not title_a or not company_a:
            continue
        date_el = item.select_one(".support_info .date")
        deadline, kind = parse_deadline(date_el.get_text() if date_el else "", today)
        place = item.select_one(".work_place")
        career = item.select_one(".career")
        out.append(
            Posting(
                posting_id=pid,
                title=(title_a.get("title") or title_a.get_text()).strip(),
                company=company_a.get_text().strip(),
                # 상세 경로는 robots.txt 일부 금지 구간이라 접속하지 않고 링크만 저장한다.
                url=f"{BASE_URL}/zf_user/jobs/relay/view?rec_idx={pid}",
                deadline=deadline,
                deadline_kind=kind,
                location=place.get_text().strip() if place else "",
                career=career.get_text().strip() if career else "",
            )
        )
    return out


def _check_blocked(resp: requests.Response) -> None:
    if resp.status_code in (403, 429):
        raise BlockedError(f"HTTP {resp.status_code}")
    if "captcha" in resp.text.lower():
        raise BlockedError("CAPTCHA 감지")


def fetch_postings(
    cat_mcls: str,
    max_count: int = 100,
    user_agent: str = "personal-job-tracker",
    session: requests.Session | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[Posting], bool]:
    """직군 코드로 공고를 최대 max_count건 가져온다. (공고 목록, 파싱 0건 경고 여부)."""
    s = session or requests.Session()
    s.headers["User-Agent"] = user_agent
    result: dict[str, Posting] = {}
    page = 1
    while len(result) < max_count:
        if page > 1:
            sleep(MIN_DELAY_SEC)
        resp = s.get(
            LIST_URL,
            params={"cat_mcls": cat_mcls, "page": page, "page_count": PAGE_COUNT},
            timeout=20,
        )
        try:
            _check_blocked(resp)
        except BlockedError as e:
            e.partial = list(result.values())[:max_count]  # 이미 가져온 공고는 반영한다
            raise
        resp.raise_for_status()
        found = parse_list(resp.text)
        if not found:
            return list(result.values())[:max_count], page == 1
        new = [p for p in found if p.posting_id not in result]
        if not new:  # 같은 페이지만 반복되면 중단
            break
        for p in new:
            result[p.posting_id] = p
        page += 1
    return list(result.values())[:max_count], False
