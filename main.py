"""사용법: python main.py --job "IT개발·데이터" [--max 100]"""
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from jobtracker import notion, sync


def main() -> int:
    load_dotenv()
    jobs = {k: v for k, v in json.loads(Path("jobs.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True, choices=sorted(jobs), help="수집할 직군")
    ap.add_argument("--max", type=int, default=100)
    args = ap.parse_args()

    try:
        token, inbox, applied = (os.environ[k] for k in ("NOTION_TOKEN", "NOTION_INBOX_DB_ID", "NOTION_APPLIED_DB_ID"))
    except KeyError as e:
        print(f"오류: .env에 {e} 가 없습니다.", file=sys.stderr)
        return 1
    ua = os.environ.get("USER_AGENT", "personal-job-tracker")

    try:
        summary = sync.run(notion.Notion(token), inbox, applied, args.job, jobs[args.job], ua, args.max)
    except notion.NotionError as e:
        print(f"노션 오류(사람인 요청 전 또는 도중 중단): {e}", file=sys.stderr)
        return 1
    print(summary.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
