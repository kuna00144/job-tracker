"""Notion API 얇은 래퍼 (requests 사용). 속성 이름은 SPEC의 DB 스키마를 따른다."""
from __future__ import annotations

import time
from datetime import date

import requests

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
MAX_RETRY = 3


class NotionError(Exception):
    pass


class Notion:
    def __init__(self, token: str, session: requests.Session | None = None):
        self.s = session or requests.Session()
        self.s.headers.update(
            {"Authorization": f"Bearer {token}", "Notion-Version": VERSION, "Content-Type": "application/json"}
        )

    def _req(self, method: str, path: str, **kw) -> dict:
        for attempt in range(MAX_RETRY + 1):
            r = self.s.request(method, f"{API}{path}", timeout=30, **kw)
            if r.status_code == 429 and attempt < MAX_RETRY:
                time.sleep(float(r.headers.get("Retry-After", "1")))
                continue
            if not r.ok:
                raise NotionError(f"{method} {path} -> {r.status_code}: {r.text[:200]}")
            return r.json()
        raise NotionError("재시도 한도 초과")

    def check_database(self, db_id: str) -> None:
        self._req("GET", f"/databases/{db_id}")

    def query_all(self, db_id: str, filter_: dict | None = None) -> list[dict]:
        pages, cursor = [], None
        while True:
            body: dict = {"page_size": 100}
            if filter_:
                body["filter"] = filter_
            if cursor:
                body["start_cursor"] = cursor
            data = self._req("POST", f"/databases/{db_id}/query", json=body)
            pages += data["results"]
            if not data.get("has_more"):
                return pages
            cursor = data["next_cursor"]

    def create_page(self, db_id: str, props: dict) -> dict:
        return self._req("POST", "/pages", json={"parent": {"database_id": db_id}, "properties": props})

    def update_page(self, page_id: str, props: dict) -> dict:
        return self._req("PATCH", f"/pages/{page_id}", json={"properties": props})

    def archive_page(self, page_id: str) -> dict:
        return self._req("PATCH", f"/pages/{page_id}", json={"archived": True})


# --- 속성 변환 헬퍼 ---
def title(v: str) -> dict:
    return {"title": [{"text": {"content": v[:2000]}}]}


def text(v: str) -> dict:
    return {"rich_text": [{"text": {"content": v[:2000]}}]}


def url(v: str) -> dict:
    return {"url": v or None}


def date_(v: date | None) -> dict:
    return {"date": {"start": v.isoformat()} if v else None}


def select(v: str) -> dict:
    return {"select": {"name": v} if v else None}


def multi_select(vs: list[str]) -> dict:
    return {"multi_select": [{"name": v} for v in vs]}


# --- 페이지 읽기 헬퍼 ---
def get_text(page: dict, name: str) -> str:
    p = page["properties"].get(name, {})
    arr = p.get("title") or p.get("rich_text") or []
    return "".join(x["plain_text"] for x in arr)


def get_date(page: dict, name: str) -> date | None:
    d = page["properties"].get(name, {}).get("date")
    return date.fromisoformat(d["start"][:10]) if d and d.get("start") else None


def get_url(page: dict, name: str) -> str:
    return page["properties"].get(name, {}).get("url") or ""


def get_multi(page: dict, name: str) -> list[str]:
    return [o["name"] for o in page["properties"].get(name, {}).get("multi_select", [])]


def get_checkbox(page: dict, name: str) -> bool:
    return bool(page["properties"].get(name, {}).get("checkbox"))
