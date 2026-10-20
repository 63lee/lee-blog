# -*- coding: utf-8 -*-
"""매일 아침 실행되는 진입점.

주제 선정 -> 초안 작성 -> 로컬 저장 -> Blogger 초안 업로드.
발행은 사람이 한다.
"""
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

from keywords import mark_used, pick_today  # noqa: E402  (load_dotenv 이후에 임포트)
from images import build_images  # noqa: E402
from writer import write_draft  # noqa: E402
import hosting  # noqa: E402
import mailer  # noqa: E402
from images import make_thumbnail  # noqa: E402

LOG_PATH = BASE / "data" / "run.log"


def output_dir() -> Path:
    """초안을 저장할 폴더.

    .env의 OUTPUT_DIR로 바꿀 수 있다. 구글 드라이브 같은 동기화 폴더를
    가리켰다가 오프라인이면 실행 전체가 죽으므로, 쓸 수 없으면 로컬로 물러난다.
    """
    configured = os.environ.get("OUTPUT_DIR", "").strip()
    fallback = BASE / "output"
    if not configured:
        return fallback

    target = Path(configured)

    # 부팅 직후에는 구글 드라이브가 아직 안 올라와 있을 수 있다.
    # 30초 간격으로 최대 5분까지 기다린 뒤에야 로컬로 물러난다.
    last_error = None
    for attempt in range(10):
        try:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return target
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                print(f"  {target} 준비를 기다리는 중 (최대 5분)")
            time.sleep(30)

    print(f"  [경고] {target} 에 쓸 수 없어 로컬로 저장합니다: {last_error}")
    return fallback


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def slugify(text: str) -> str:
    return re.sub(r"[^\w가-힣]+", "-", text).strip("-")[:40]


def save_local(draft: dict, index: int) -> Path:
    """검수용 HTML 파일로 저장한다. Blogger 업로드가 실패해도 원고는 남는다."""
    today = datetime.now().strftime("%Y-%m-%d")
    day_dir = output_dir() / today
    day_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{index:02d}-{slugify(draft['titles'][0])}"
    path = day_dir / f"{stem}.html"

    imgs = build_images(draft, day_dir, stem)
    draft["_imgs"] = imgs  # 업로드 단계에서 저장소에 올려 본문에 넣는다
    draft["_img_dir"] = day_dir / f"{stem}-images"

    img_block = ""
    if imgs["stock"]:
        st = imgs["stock"]
        img_block += (
            f'<p><img src="./{stem}-images/{st["path"].name}" style="max-width:100%"><br>'
            f'<small>도입부 사진 · ⓒ {st["photographer"]} / Pexels</small></p>'
        )
    for i, card in enumerate(imgs["cards"], 1):
        img_block += (
            f'<p><img src="./{stem}-images/card{i}.png" style="max-width:100%"></p>'
        )
    if img_block:
        img_block = "<p><b>이미지</b> (Blogger 편집기에 드래그해 넣으세요)</p>" + img_block

    title_block = "".join(
        f"<li><strong>{t}</strong><br><small>{n}</small></li>"
        for t, n in zip(draft["titles"], draft.get("title_notes", [""] * 3))
    )
    check_block = "".join(f"<li>{c}</li>" for c in draft.get("fact_check_notes", []))

    asset_names = {
        "template": "양식 템플릿",
        "examples": "예시 문장 모음",
        "table": "계산·기준 표",
        "checklist": "체크리스트",
        "none": "없음 (에세이형)",
    }
    asset_type = draft.get("asset_type", "none")
    asset_block = (
        f"<p><b>실용 자산</b> {asset_names.get(asset_type, asset_type)}"
        f" — <small>{draft.get('asset_reason', '')}</small></p>"
    )

    path.write_text(
        f"""<!doctype html><meta charset="utf-8">
<title>{draft['titles'][0]}</title>
<style>body{{max-width:720px;margin:40px auto;padding:0 20px;font:16px/1.8 system-ui,sans-serif}}
.box{{background:#f6f6f6;padding:16px 20px;border-radius:8px;margin-bottom:24px;font-size:14px}}
h2{{margin-top:2em}}
table{{width:100%;border-collapse:collapse;margin:1.5em 0;font-size:15px}}
th,td{{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}}
th{{background:#f0f0f0}}</style>
<div class="box">
<p><b>주제</b> {draft['topic']['keyword']} ({draft['topic']['track']} / {draft['topic']['category']})</p>
<p><b>제목 후보</b></p><ol>{title_block}</ol>
<p><b>메타 설명</b> {draft.get('meta_description','')}</p>
<p><b>라벨</b> {', '.join(draft.get('labels', []))}</p>
{asset_block}
<p><b>발행 전 팩트체크</b></p><ul>{check_block}</ul>
{img_block}
</div>
<h1>{draft['titles'][0]}</h1>
{draft['body_html']}
""",
        encoding="utf-8",
    )
    return path


def topics_from_args(argv: list[str]) -> list[dict]:
    """--topic "주제" 로 직접 지정한 주제들. 다시 뽑거나 특정 글을 쓸 때 쓴다."""
    picked = []
    for i, arg in enumerate(argv):
        if arg == "--topic" and i + 1 < len(argv):
            picked.append(
                {
                    "keyword": argv[i + 1],
                    "traffic": "-",
                    "headlines": [],
                    "score": 0,
                    "category": "career",
                    "track": "manual",
                }
            )
    return picked


def _img(url: str, alt: str, caption: str = "") -> str:
    cap = (f'<br><small style="color:#8a8178;">{caption}</small>') if caption else ""
    return (f'<p style="text-align:center;"><img src="{url}" alt="{alt}" '
            f'style="max-width:100%;height:auto;border-radius:8px;" />{cap}</p>')


def with_images(draft: dict) -> str:
    """썸네일·도입부 사진·인용 카드를 저장소에 올리고 본문에 넣은 HTML 을 돌려준다.

    - 썸네일(모바일 세로)은 맨 위: Blogger 는 첫 이미지를 목록 썸네일로 쓴다.
    - 도입부 사진은 첫 문단 뒤, 인용 카드는 두 번째·마지막 소제목 앞.
    """
    body = draft["body_html"]
    imgs = draft.get("_imgs") or {"cards": [], "stock": None}
    title = draft["titles"][0]
    # Pixabay 사진이 있으면 사진 배경 썸네일, 없으면 남색 글자 썸네일
    hero_photo = imgs["stock"]["path"] if imgs.get("stock") else None
    thumb = make_thumbnail(title, draft["_img_dir"] / "thumb.png", photo=hero_photo)
    draft["_thumb"] = thumb
    extra = imgs.get("photos", [])
    files = ([thumb] + list(imgs["cards"]) + ([imgs["stock"]["path"]] if imgs["stock"] else [])
             + [p["path"] for p in extra])
    urls = hosting.publish(files, f"images: {title[:40]}")

    # 도입부 사진은 이미 썸네일 배경으로 썼으므로 본문에 다시 넣지 않는다

    # 본문 중간 사진: 세 번째 소제목 앞 (인용 카드와 겹치지 않게)
    if extra:
        h2s = [m.start() for m in re.finditer(r"<h2", body)]
        pos = h2s[2] if len(h2s) >= 4 else (h2s[-1] if h2s else len(body))
        body = body[:pos] + _img(urls[extra[0]["path"]], draft.get("image_query", title)) + body[pos:]

    h2 = [m.start() for m in re.finditer(r"<h2", body)]
    spots = []
    if len(h2) >= 2:
        spots.append(h2[1])
    if len(h2) >= 3:
        spots.append(h2[-1])
    # 뒤에서부터 넣어야 앞쪽 위치가 밀리지 않는다
    for card, pos in sorted(zip(imgs["cards"], spots), key=lambda x: -x[1]):
        body = body[:pos] + _img(urls[card], "핵심 문장 카드") + body[pos:]
    for card in imgs["cards"][len(spots):]:
        body += _img(urls[card], "핵심 문장 카드")

    return _img(urls[thumb], title) + body


def save_naver_version(draft: dict, url: str) -> None:
    """네이버 블로그용으로 다시 쓴 원고와 사진을 구글 드라이브에 저장한다. 실패해도 발행에는 영향 없음."""
    import naver
    import gdrive
    if not gdrive.enabled():
        # 2026-10-17: 조용히 건너뛰어서 네이버용 원고가 안 생긴 걸 몰랐다. 반드시 로그를 남긴다.
        log("  [경고] 네이버용 원고 건너뜀: 드라이브 권한(GDRIVE_* / token_drive.json) 없음")
        return
    try:
        from anthropic import Anthropic
        from writer import MODEL
        imgs = draft.get("_imgs") or {}
        photos = ([draft["_thumb"]] if draft.get("_thumb") else [])
        photos += ([imgs["stock"]["path"]] if imgs.get("stock") else [])
        photos += [p["path"] for p in imgs.get("photos", [])] + list(imgs.get("cards", []))
        post = naver.write(Anthropic(), MODEL, draft["titles"][0], draft.get("_search_keyword", ""),
                           url, draft["body_html"], len(photos),
                           extra="\n".join([
                               "- 글쓴이는 회사 생활을 오래 한 직장 선배 '역삼동이선생'. '25년' 같은 경력 연수는 쓰지 않는다. **평어체**(~다, ~한다)로 쓴다. 존댓말 금지.",
                               "- 이선생은 **여성**이고 딸 써니가 있다. 후배는 '선배'라고 부른다('형'·'오빠' 금지).",
                               "- 목적은 **인플루언서·팬 확보**다. 정보 정리보다 이선생 본인의 경험·감정·후배를 아끼는 "
                               "시선이 보이게 쓴다. 첫 문단은 이선생의 구체적인 장면으로 시작한다.",
                               "- 끝에 독자 경험을 묻는 댓글 질문 1개와 '이런 이야기가 도움이 됐다면 이웃 추가해 두세요' 같은 한 줄.",
                               "- 원문 링크는 '더 자세한 정리는 여기'처럼 가볍게 한 번만.",
                           ]))
        out = Path(draft["_img_dir"]).parent / (Path(draft["_img_dir"]).name + "-naver")
        files = naver.package(post, photos, out)
        where = gdrive.save("이선생", datetime.now().strftime("%Y-%m-%d"), post["title"], files)
        log(f"  네이버용 원고 저장: 구글 드라이브/{where}")
    except Exception as exc:
        log(f"  [경고] 네이버용 원고 저장 실패 ({type(exc).__name__}: {exc})")


def save_clip(draft: dict) -> bool:
    """글로 네이버 클립·인스타 릴스 영상(9:16)을 만들어 드라이브 '[클립] 제목' 폴더에 저장한다 (2026-10-20).
    영상·표지·캡션 2개가 들어간다. 대본 JSON 은 posts/ 에 남긴다. 실패해도 발행에는 영향 없음."""
    import gdrive
    if os.environ.get("CLIP_MODE", "drive") == "off":
        return False
    if not gdrive.enabled():
        log("  [경고] 클립 건너뜀: 드라이브 권한 없음")
        return False
    try:
        import json
        import tempfile
        from anthropic import Anthropic
        import clip
        import clipwriter
        from writer import MODEL
        client = Anthropic()
        title = draft["titles"][0]
        job = clipwriter.make_job(client, MODEL, title, draft["body_html"])
        # 영상 작업 파일(배경 영상 등)은 저장소에 올리지 않도록 임시 폴더에서 만든다
        tmp = Path(tempfile.mkdtemp())
        job_path = tmp / "clip.json"
        job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        out = tmp / "out"
        final = clip.build(job_path, picker=clip.vision_picker(client, MODEL, job["title"]), out=out)
        img_dir = Path(draft["_img_dir"])
        (img_dir.parent / (img_dir.name.replace("-images", "") + "-clip.json")).write_text(
            job_path.read_text(encoding="utf-8"), encoding="utf-8")
        files = [p for p in (final, out / "cover.jpg", out / "caption_naver.txt", out / "caption_instagram.txt")
                 if p.exists()]
        where = gdrive.save("이선생", datetime.now().strftime("%Y-%m-%d"), f"[클립] {title}", files)
        log(f"  클립 저장: 구글 드라이브/{where}")
        return True
    except Exception as exc:
        log(f"  [경고] 클립 만들기 실패 ({type(exc).__name__}: {exc})")
        traceback.print_exc()
        return False


def main() -> int:
    manual = topics_from_args(sys.argv)
    count = len(manual) or int(os.environ.get("DRAFTS_PER_DAY", "2"))
    log(f"=== 시작 (초안 {count}개) ===")

    topics = manual or pick_today(count)
    if not topics:
        log("쓸 주제가 없습니다. niche.py의 EVERGREEN_TOPICS를 보충하세요.")
        return 1

    upload = "--no-upload" not in sys.argv
    failures = 0
    clips_made = 0

    for i, topic in enumerate(topics, 1):
        log(f"[{i}/{len(topics)}] {topic['track']} / {topic['keyword']}")
        try:
            draft = write_draft(topic)
        except Exception as exc:
            log(f"  초안 작성 실패: {exc}")
            traceback.print_exc()
            failures += 1
            continue

        draft["_search_keyword"] = topic.get("search_keyword", "")
        mark_used(topic)
        path = save_local(draft, i)
        log(f"  저장: {path}")

        if not upload:
            continue
        try:
            from publisher import create_draft

            body = with_images(draft) if hosting.enabled() else draft["body_html"]
            title = draft["titles"][0]
            if mailer.enabled():
                # 이 계정은 API 글쓰기가 막혀 있어 '이메일로 게시'로 올린다 (라벨 대신 태그 줄을 붙인다)
                tags = " ".join(f"#{t.replace(' ', '')}" for t in draft.get("labels", []))
                if tags:
                    body += f'<p style="color:#8a8178;font-size:14px;">{tags}</p>'
                mailer.send(title, body)
                url = mailer.wait_published(title)
                log(f"  메일로 게시: {url or '발송 완료 (피드 반영 대기 중)'}")
                save_naver_version(draft, url)
                # 클립은 하루 CLIPS_PER_DAY 편(기본 1편)만 만든다
                if clips_made < int(os.environ.get("CLIPS_PER_DAY", "1")) and save_clip(draft):
                    clips_made += 1
                continue
            post = create_draft(title, body, draft.get("labels", []))
            log(f"  Blogger 초안 등록: {post.get('url') or post.get('id')}")
        except Exception as exc:
            # 업로드가 실패해도 로컬 원고는 남아 있으니 치명적이지 않다.
            log(f"  Blogger 업로드 실패 (로컬 파일은 남아 있음): {exc}")
            failures += 1

    log(f"=== 완료 (실패 {failures}건) ===")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
