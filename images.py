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


def make_thumbnail(title: str, out_path: Path, label: str = "역삼동이선생의 슬기로운 직장생활") -> Path:
    """글 맨 위에 들어갈 모바일 세로 썸네일. Blogger 는 첫 이미지를 목록 썸네일로 쓴다."""
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


def fetch_stock_photo(query: str, out_path: Path) -> dict | None:
    """Pexels에서 도입부용 사진 한 장을 받는다. 키가 없거나 실패하면 None."""
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        return None

    url = (
        "https://api.pexels.com/v1/search?"
        + urllib.parse.urlencode(
            {"query": query, "per_page": 1, "orientation": "landscape", "size": "large"}
        )
    )
    try:
        import json

        req = urllib.request.Request(url, headers={"Authorization": key})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read())
        if not data.get("photos"):
            return None
        photo = data["photos"][0]

        out_path.parent.mkdir(parents=True, exist_ok=True)
        img_req = urllib.request.Request(
            photo["src"]["large2x"], headers={"User-Agent": "Mozilla/5.0"}
        )
        out_path.write_bytes(urllib.request.urlopen(img_req, timeout=30).read())
        return {
            "path": out_path,
            "photographer": photo.get("photographer", ""),
            "source_url": photo.get("url", ""),
        }
    except Exception as exc:
        print(f"  [경고] 스톡 사진 실패: {exc}")
        return None


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
    if query:
        result["stock"] = fetch_stock_photo(query, img_dir / "hero.jpg")

    return result
