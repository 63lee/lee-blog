# -*- coding: utf-8 -*-
"""포스팅에 넣을 이미지를 준비한다.

두 종류를 만든다.
  1) 인용 카드 — 글의 핵심 문장을 담은 PNG. 직접 그리므로 저작권 문제가 없고
     글 내용과 정확히 맞는다.
  2) 도입부 스톡 사진 — Pexels에서 받는다. 상업적 이용과 핫링크가 허용된다.
     PEXELS_API_KEY가 없으면 이 단계는 조용히 건너뛴다.

Blogger API에는 이미지 업로드가 없어서, 파일로만 저장하고 사람이
검수하면서 Blogger 편집기에 드래그해 넣는다.
"""
import os
import re
import textwrap
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CARD_W, CARD_H = 1200, 630
def _first(*paths: str) -> Path:
    """윈도우(로컬)와 리눅스(GitHub Actions, fonts-nanum) 어느 쪽에서든 한글 글꼴을 찾는다."""
    for p in paths:
        if Path(p).exists():
            return Path(p)
    return Path(paths[0])


FONT_BOLD = _first("C:/Windows/Fonts/malgunbd.ttf",
                   "/usr/share/fonts/truetype/nanum/NanumGothicExtraBold.ttf",
                   "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf")
FONT_REG = _first("C:/Windows/Fonts/malgun.ttf",
                  "/usr/share/fonts/truetype/nanum/NanumGothic.ttf")

# 어두운 남색 바탕에 크림색 글씨. 채도를 낮춰서 본문 읽기를 방해하지 않는다.
BG = (23, 32, 47)
FG = (243, 240, 233)
ACCENT = (198, 164, 106)


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def make_quote_card(quote: str, out_path: Path, byline: str = "역삼동이선생") -> Path:
    """핵심 문장 하나를 담은 인용 카드를 그린다."""
    img = Image.new("RGB", (CARD_W, CARD_H), BG)
    d = ImageDraw.Draw(img)

    # 왼쪽 세로 악센트 바
    d.rectangle([80, 150, 88, CARD_H - 150], fill=ACCENT)

    # 글자 수에 따라 크기를 줄여 카드 밖으로 넘치지 않게 한다
    if len(quote) <= 40:
        size, width = 54, 18
    elif len(quote) <= 70:
        size, width = 44, 23
    else:
        size, width = 36, 28

    lines = textwrap.wrap(quote, width=width)[:6]
    font = _font(FONT_BOLD, size)
    line_h = int(size * 1.55)
    total_h = line_h * len(lines)
    y = (CARD_H - total_h) // 2 - 20

    for line in lines:
        d.text((130, y), line, font=font, fill=FG)
        y += line_h

    d.text((130, CARD_H - 110), byline, font=_font(FONT_REG, 26), fill=ACCENT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


THUMB_W, THUMB_H = 1080, 1350  # 모바일 세로 썸네일 (4:5)


def make_thumbnail(title: str, out_path: Path, label: str = "역삼동이선생의 슬기로운 직장생활",
                   photo: Path | None = None) -> Path:
    """글 맨 위에 들어갈 모바일 세로 썸네일. Blogger 는 첫 이미지를 목록 썸네일로 쓴다.

    photo(Pixabay 사진)가 있으면 사진 위에 제목을 얹고, 없으면 남색 배경 버전으로 만든다.
    """
    if photo and Path(photo).exists():
        try:
            return _photo_thumbnail(title, out_path, Path(photo))
        except Exception as exc:
            print(f"  [경고] 사진 썸네일 실패, 기본 썸네일로 대신 ({type(exc).__name__})")
    img = Image.new("RGB", (THUMB_W, THUMB_H), BG)
    d = ImageDraw.Draw(img)

    # 위쪽 라벨
    f_label = _font(FONT_BOLD, 38)
    d.rectangle([80, 230, 88, 290], fill=ACCENT)
    d.text((112, 236), label, font=f_label, fill=ACCENT)

    # 제목: 쉼표·대시 기준으로 나눈 뒤 폭에 맞춰 줄바꿈, 최대 5줄
    parts = [p.strip() for p in title.replace("—", ",").split(",") if p.strip()] or [title]
    size = 92
    while size >= 60:
        font = _font(FONT_BOLD, size)
        lines = []
        for part in parts:
            cur = ""
            for word in part.split(" "):
                trial = f"{cur} {word}".strip()
                if d.textlength(trial, font=font) <= THUMB_W - 180:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = word
            lines.append(cur)
        if len(lines) <= 5:
            break
        size -= 8
    y = 380
    for line in lines[:5]:
        d.text((90, y), line, font=font, fill=FG)
        y += int(size * 1.35)

    d.line([90, THUMB_H - 190, THUMB_W - 90, THUMB_H - 190], fill=ACCENT, width=2)
    d.text((90, THUMB_H - 160), "역삼동이선생", font=_font(FONT_BOLD, 40), fill=FG)
    d.text((90, THUMB_H - 105), "63lee.blogspot.com", font=_font(FONT_REG, 30), fill=ACCENT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path


USED_PHOTOS = Path(__file__).parent / "data" / "used_photos.json"


def _used_ids() -> set:
    try:
        import json
        return set(json.loads(USED_PHOTOS.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _mark_used(pid: str) -> None:
    import json
    ids = sorted(_used_ids() | {pid})
    USED_PHOTOS.parent.mkdir(parents=True, exist_ok=True)
    USED_PHOTOS.write_text(json.dumps(ids), encoding="utf-8")


def fetch_stock_photos(query: str, out_dir: Path, count: int = 2,
                       title: str = "", summary: str = "") -> list[dict]:
    """Pixabay 에서 사진을 count 장 받는다 (2026-10-16, Pexels 신규 키 중단으로 교체).

    Pixabay 라이선스: 상업적 이용 가능, 출처 표기 의무 없음. 단 사진 주소 직접 연결(핫링크)은
    허용되지 않아 내려받아 저장소에 올려 쓴다. 이미 쓴 사진은 다시 쓰지 않는다.
    PIXABAY_API_KEY 가 없거나 실패하면 빈 목록.
    """
    import json

    key = os.environ.get("PIXABAY_API_KEY", "").strip().strip('"').strip("'")
    if not key or not query:
        return []
    url = "https://pixabay.com/api/?" + urllib.parse.urlencode({
        "key": key, "q": query, "image_type": "photo", "orientation": "horizontal",
        "safesearch": "true", "per_page": 30, "min_width": 1200, "order": "popular"})
    try:
        # User-Agent 가 없으면 Pixabay(Cloudflare)가 403(1010)으로 막는다
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (lee-blog)"})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read())
    except Exception as exc:
        # 오류 메시지에 키가 든 주소가 찍히지 않게 종류만 남긴다
        print(f"  [경고] Pixabay 검색 실패 ({type(exc).__name__})")
        return []

    used = _used_ids()
    hits = [h for h in data.get("hits", []) if f"pixabay-{h['id']}" not in used]

    # Claude 가 미리보기를 보고 썸네일용(첫 번째)·본문용을 고른다. 실패하면 인기순 그대로.
    if title and len(hits) >= 3 and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from anthropic import Anthropic
            from writer import MODEL
            import vision
            pick = vision.choose(Anthropic(), MODEL, title, summary,
                                 [h["webformatURL"] for h in hits[:10]], count - 1)
            if pick:
                order = [pick["thumb"]] + pick["body"]
                hits = [hits[i] for i in order]
        except Exception as exc:
            print(f"  [경고] 사진 선택 건너뜀 ({type(exc).__name__})")

    out = []
    for hit in hits:
        pid = f"pixabay-{hit['id']}"
        try:
            path = out_dir / f"photo{len(out) + 1}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(hit["largeImageURL"], headers={"User-Agent": "Mozilla/5.0"})
            path.write_bytes(urllib.request.urlopen(req, timeout=30).read())
        except Exception as exc:
            print(f"  [경고] 사진 내려받기 실패 ({type(exc).__name__})")
            continue
        _mark_used(pid)
        out.append({"path": path, "photographer": hit.get("user", ""),
                    "source_url": hit.get("pageURL", ""), "tags": hit.get("tags", "")})
        if len(out) >= count:
            break
    return out


def _title_lines(d, title: str, font, max_w: int) -> list:
    parts = [p.strip() for p in title.replace("—", ",").split(",") if p.strip()] or [title]
    lines = []
    for part in parts:
        cur = ""
        for word in part.split(" "):
            trial = f"{cur} {word}".strip()
            if d.textlength(trial, font=font) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return [l for l in lines if l]


def _photo_thumbnail(title: str, out_path: Path, photo: Path) -> Path:
    """사진 배경 썸네일 (아로하 블로그와 같은 구성: 라벨 알약 → 가는 선 → 굵은 제목)."""
    from PIL import ImageFilter

    img = Image.open(photo).convert("RGB")
    scale = max(THUMB_W / img.width, THUMB_H / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - THUMB_W) // 2, (img.height - THUMB_H) // 2
    img = img.crop((left, top, left + THUMB_W, top + THUMB_H))

    # 제목이 놓이는 위쪽과 맨 아래를 어둡게
    col = [int(min(200 * max(0.0, 1 - (y / THUMB_H) / 0.70) + 190 * max(0.0, (y / THUMB_H - 0.78) / 0.22), 215))
           for y in range(THUMB_H)]
    mask = Image.new("L", (1, THUMB_H))
    mask.putdata(col)
    img = Image.composite(Image.new("RGB", img.size, (12, 18, 30)), img, mask.resize(img.size))

    d = ImageDraw.Draw(img)
    f_label = _font(FONT_BOLD, 38)
    a, b = "역삼동이선생의", "슬기로운 직장생활"
    tw = d.textlength(f"{a} {b}", font=f_label)
    box = (60, 210, 60 + tw + 88, 210 + 82)
    pill = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle(box, radius=41, fill=(250, 248, 244, 235))
    img = Image.alpha_composite(img.convert("RGBA"), pill).convert("RGB")
    d = ImageDraw.Draw(img)
    d.text((box[0] + 44, box[1] + 18), a, font=f_label, fill=(23, 32, 47))
    d.text((box[0] + 44 + d.textlength(a + " ", font=f_label), box[1] + 18), b, font=f_label, fill=ACCENT)

    line_y = box[3] + 52
    d.line((60, line_y, THUMB_W - 60, line_y), fill=(255, 255, 255), width=3)

    size = 92
    while True:
        font = _font(FONT_BOLD, size)
        lines = _title_lines(d, title, font, THUMB_W - 120)
        if len(lines) <= 4 or size <= 60:
            break
        size -= 6
    y = line_y + 56
    for ln in lines[:4]:
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).text((62, y + 4), ln, font=font, fill=(0, 0, 0, 150))
        img = Image.alpha_composite(img.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(6))).convert("RGB")
        d = ImageDraw.Draw(img)
        d.text((60, y), ln, font=font, fill=(255, 255, 255))
        y += int(size * 1.3)

    d.text((60, THUMB_H - 128), "역삼동이선생", font=_font(FONT_BOLD, 38), fill=(255, 255, 255))
    d.text((60, THUMB_H - 76), "63lee.blogspot.com", font=_font(FONT_REG, 28), fill=ACCENT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path.with_suffix(".jpg"), "JPEG", quality=86, optimize=True, progressive=True)
    return out_path.with_suffix(".jpg")


def fetch_stock_photo(query: str, out_path: Path) -> dict | None:
    """예전 호출 호환용: 사진 한 장."""
    photos = fetch_stock_photos(query, out_path.parent, 1)
    return photos[0] if photos else None


def build_images(draft: dict, day_dir: Path, stem: str) -> dict:
    """초안 하나에 딸린 이미지를 모두 만든다.

    폴더 이름은 글 파일명(stem)을 따른다. 순번으로만 지으면 같은 날
    다시 실행했을 때 앞서 만든 글의 이미지를 덮어쓴다.
    """
    result = {"cards": [], "stock": None}
    img_dir = day_dir / f"{stem}-images"

    for i, quote in enumerate(draft.get("quote_cards", [])[:2], 1):
        try:
            result["cards"].append(make_quote_card(quote, img_dir / f"card{i}.png"))
        except Exception as exc:
            print(f"  [경고] 인용 카드 생성 실패: {exc}")

    query = draft.get("image_query")
    summary = re.sub(r"<[^>]+>", " ", draft.get("body_html", ""))[:600]
    photos = fetch_stock_photos(query, img_dir, 2, draft.get("titles", [""])[0], summary) if query else []
    result["stock"] = photos[0] if photos else None
    result["photos"] = photos[1:]

    return result
