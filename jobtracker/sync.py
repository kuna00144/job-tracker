"""SPEC의 실행 순서: 사전점검 -> 이동 -> 정리 -> 수집 -> 반영 -> 요약."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from . import notion as n
from .saramin import BlockedError, Posting, fetch_postings

# 노션 속성 이름 (SPEC 스키마)
P_TITLE, P_COMPANY, P_ID, P_URL, P_DEADLINE = "공고명", "회사명", "공고ID", "URL", "마감일"
P_KIND, P_LOC, P_CAREER, P_JOBS, P_COLLECTED, P_APPLY = "마감구분", "근무지", "경력", "직군", "수집일", "지원할래"


@dataclass
class Summary:
    new: int = 0
    updated: int = 0
    moved: int = 0
    cleaned: int = 0
    warnings: list[str] = field(default_factory=list)

    def render(self) -> str:
        line = f"신규 {self.new} / 갱신 {self.updated} / 이동 {self.moved} / 정리 {self.cleaned}"
        return line + "".join(f"\n경고: {w}" for w in self.warnings)


def precheck(client: n.Notion, inbox_id: str, applied_id: str) -> None:
    """사람인에 요청을 보내기 전에 노션 접근부터 확인한다."""
    client.check_database(inbox_id)
    client.check_database(applied_id)


def move_applied(client: n.Notion, inbox_id: str, applied_id: str, s: Summary) -> None:
    """지원할래 체크된 공고를 지원현황에 생성 -> 성공 확인 후 수집함에서 삭제."""
    checked = client.query_all(inbox_id, {"property": P_APPLY, "checkbox": {"equals": True}})
    if not checked:
        return
    existing = {n.get_text(p, P_ID) for p in client.query_all(applied_id)}
    for page in checked:
        pid = n.get_text(page, P_ID)
        if pid not in existing:
            client.create_page(
                applied_id,
                {
                    P_TITLE: n.title(n.get_text(page, P_TITLE)),
                    P_COMPANY: n.text(n.get_text(page, P_COMPANY)),
                    P_ID: n.text(pid),
                    P_URL: n.url(n.get_url(page, P_URL)),
                    P_DEADLINE: n.date_(n.get_date(page, P_DEADLINE)),
                    "지원상태": n.select("지원 전"),
                },
            )  # 예외가 나면 여기서 중단 -> 삭제하지 않는다
            existing.add(pid)
            s.moved += 1
        client.archive_page(page["id"])


def cleanup_expired(client: n.Notion, inbox_id: str, s: Summary, today: date) -> None:
    """마감일이 오늘 이전인 공고 삭제. 마감일이 비어 있으면(상시/채용시) 건드리지 않는다."""
    expired = client.query_all(
        inbox_id, {"property": P_DEADLINE, "date": {"before": today.isoformat()}}
    )
    for page in expired:
        client.archive_page(page["id"])
        s.cleaned += 1


def apply_postings(
    client: n.Notion, inbox_id: str, applied_id: str, postings: list[Posting], job: str, s: Summary, today: date
) -> None:
    applied_ids = {n.get_text(p, P_ID) for p in client.query_all(applied_id)}
    inbox = {n.get_text(p, P_ID): p for p in client.query_all(inbox_id)}
    for p in postings:
        if p.posting_id in applied_ids:
            continue
        fields = {
            P_TITLE: n.title(p.title),
            P_COMPANY: n.text(p.company),
            P_URL: n.url(p.url),
            P_DEADLINE: n.date_(p.deadline),
            P_KIND: n.select(p.deadline_kind),
            P_LOC: n.text(p.location),
            P_CAREER: n.text(p.career),
        }
        page = inbox.get(p.posting_id)
        if page:
            jobs = n.get_multi(page, P_JOBS)
            if job not in jobs:
                jobs.append(job)
            client.update_page(page["id"], {**fields, P_JOBS: n.multi_select(jobs)})
            s.updated += 1
        else:
            client.create_page(
                inbox_id,
                {
                    **fields,
                    P_ID: n.text(p.posting_id),
                    P_JOBS: n.multi_select([job]),
                    P_COLLECTED: n.date_(today),
                },
            )
            s.new += 1


def run(client: n.Notion, inbox_id: str, applied_id: str, job: str, cat_mcls: str, user_agent: str,
        max_count: int = 100, today: date | None = None, fetch=fetch_postings) -> Summary:
    today = today or date.today()
    s = Summary()
    precheck(client, inbox_id, applied_id)
    move_applied(client, inbox_id, applied_id, s)
    cleanup_expired(client, inbox_id, s, today)
    postings: list[Posting] = []
    try:
        postings, empty = fetch(cat_mcls, max_count, user_agent=user_agent)
        if empty:
            s.warnings.append("응답은 정상인데 공고가 0건 파싱됨: 사이트 구조 변경 의심")
    except BlockedError as e:
        postings = list(e.partial)
        s.warnings.append(f"차단 감지({e}): 수집을 중단했습니다. 우회하지 않습니다.")
    apply_postings(client, inbox_id, applied_id, postings, job, s, today)
    return s
