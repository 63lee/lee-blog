# -*- coding: utf-8 -*-
"""이미 만들어둔 검수용 HTML을 Blogger 초안으로 올린다.

run.py가 저장한 파일에서 제목·라벨·본문을 뽑아 올린다.
같은 파일을 두 번 올리지 않도록 기록을 남긴다.

사용법:
    python upload_drafts.py "G:/내 드라이브/blog-drafts/출장-예약분/2026-09-07"
"""
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).parent
load_dotenv(BASE / ".env", override=True)

from publisher import create_draft  # noqa: E402

LOG_PATH = BASE / "data" / "uploaded.json"


def load_uploaded() -> dict:
    if LOG_PATH.exists():
        return json.loads(LOG_PATH.read_text(encoding="utf-8"))
    return {}


def parse(path: Path) -> dict:
    """검수용 HTML에서 Blogger에 올릴 내용을 추출한다."""
    html = path.read_text(encoding="utf-8")

    title = re.search(r"<title>(.*?)</title>", html, re.S).group(1).strip()

    labels = []
    m = re.search(r"<b>라벨</b>\s*([^<]*)</p>", html)
    if m:
        labels = [x.strip() for x in m.group(1).split(",") if x.strip()]

    # 검수용 박스(</div>) 뒤가 실제 본문. 제목은 Blogger가 따로 다루므로 h1을 뺀다.
    body = html.split("</div>", 1)[1]
    body = re.sub(r"<h1>.*?</h1>", "", body, flags=re.S).strip()

    # 팩트체크 목록은 HTML 주석으로 넣는다. 발행해도 독자에게 보이지 않고,
    # Blogger 편집기의 HTML 보기에서는 확인할 수 있다.
    notes = re.findall(r"<li>(.*?)</li>", html.split("팩트체크")[1].split("</ul>")[0], re.S)
    if notes:
        cleaned = [re.sub(r"<[^>]+>", "", n).strip().replace("--", "—") for n in notes]
        banner = "<!-- 발행 전 확인:\n" + "\n".join(f"  - {c}" for c in cleaned) + "\n-->\n"
        body = banner + body

    return {"title": title, "labels": labels, "body": body}


def pending(folder: str) -> list[Path]:
    """아직 안 올린 파일 목록."""
    uploaded = load_uploaded()
    return [f for f in sorted(Path(folder).glob("*.html")) if str(f.resolve()) not in uploaded]


def main(folder: str, dry_run: bool = False) -> int:
    files = sorted(Path(folder).glob("*.html"))
    if not files:
        print(f"{folder} 에 html 파일이 없습니다.")
        return 1

    todo = pending(folder)
    print(f"전체 {len(files)}건 · 이미 올림 {len(files) - len(todo)}건 · 올릴 것 {len(todo)}건")
    if dry_run:
        for f in todo:
            print(f"  대기  {parse(f)['title']}")
        return 0
    if not todo:
        return 0

    # 글 사이 간격은 publisher가 잡는다. 여기서는 진행 상황만 보여준다.
    print(f"예상 소요: 약 {len(todo) * 20 // 60 + 1}분\n")

    uploaded = load_uploaded()
    done = failed = 0
    for i, f in enumerate(todo, 1):
        d = parse(f)
        print(f"[{i}/{len(todo)}] {d['title']}")
        try:
            post = create_draft(d["title"], d["body"], d["labels"])
            uploaded[str(f.resolve())] = {"post_id": post["id"], "title": d["title"]}
            LOG_PATH.write_text(
                json.dumps(uploaded, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print("    올림")
            done += 1
        except Exception as exc:
            print(f"    실패: {str(exc)[:120]}")
            failed += 1
            # 막힌 상태에서 계속 두드리면 차단이 길어진다
            if "403" in str(exc) or "속도 제한" in str(exc):
                print("\n  Blogger가 쓰기를 막고 있습니다. 여기서 중단합니다.")
                print("  몇 시간 뒤 같은 명령을 다시 실행하면 남은 것부터 이어서 올립니다.")
                break

    print(f"\n올림 {done} · 실패 {failed} · 남음 {len(pending(folder))}")
    return 1 if failed else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(args[0] if args else "output", "--dry-run" in sys.argv))
