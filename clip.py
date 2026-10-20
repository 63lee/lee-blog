# -*- coding: utf-8 -*-
"""블로그 글 → 네이버 클립(9:16 세로 영상) 샘플 (2026-10-20).

참고 클립(어썸코리아·출근노비네) 형식:
  상단 고정 2줄 제목(흰색 + 노랑) / 화면 중앙 아래 큰 자막(강조어 노랑) / 장면마다 배경 영상 교체 /
  내레이션(edge-tts 무료 음성) / 마지막 장면은 네이버 검색창 안내.
배경 영상은 Pixabay(.env 의 PIXABAY_API_KEY), 없으면 Pexels(PEXELS_API_KEY) 무료 영상. 둘 다 출처 표기 불필요.

사용: python clip.py clip_samples/hoesik.json  → clip_samples/hoesik/ 에 mp4·캡션 저장
"""
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).parent
W, H, FPS = 1080, 1920, 30
FONT = ROOT / "fonts" / "Pretendard-SemiBold.otf"
SUB_FONT = FONT
TITLE_FONT = ROOT / "fonts" / "GowunBatang-Bold.ttf"
WHITE = (255, 255, 255)
ACCENT = (255, 214, 140)
NAVER = (3, 199, 90)


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


FF = ffmpeg_exe()


def run(args):
    # -nostdin: 이미지 반복 입력이 있으면 ffmpeg 가 키 입력을 기다리며 멈출 때가 있다
    subprocess.run([FF, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args], check=True,
                   stdin=subprocess.DEVNULL)


def duration(path: Path) -> float:
    out = subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def env(key: str) -> str:
    if os.environ.get(key):
        return os.environ[key]
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""


# ---------- 음성 ----------
async def _tts(text, voice, rate, path):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(path))


def tts(text, voice, rate, path: Path) -> float:
    if not path.exists():
        asyncio.run(_tts(text, voice, rate, path))
    return duration(path)


# ---------- 배경 영상 ----------
def _download(url: str, path: Path, headers=None) -> Path:
    if not path.exists():
        with requests.get(url, stream=True, timeout=120, headers=headers) as resp:
            resp.raise_for_status()
            with open(path, "wb") as fh:
                for chunk in resp.iter_content(1 << 16):
                    fh.write(chunk)
    return path


# 노출 많은 인물·침실 장면은 이선생 채널 톤과 맞지 않는다 (2026-10-20 사용자 지적: 슬립 차림 여성 사진)
BLOCK_TAGS = {"bed", "bedroom", "lingerie", "underwear", "bikini", "swimsuit", "sexy", "model",
              "erotic", "nightgown", "pajamas", "sleepwear", "beach", "fashion", "body", "skin",
              "woman", "girl", "lady", "legs", "heels", "feet", "shoes", "pumpkin", "aerial", "drone"}


def brightness(path: Path) -> float:
    """영상 1초 지점 프레임의 평균 밝기 (0~255)."""
    frame = path.with_suffix(".jpg")
    if not frame.exists():
        run(["-ss", "1", "-i", str(path), "-vf", "scale=90:160", "-frames:v", "1", str(frame)])
    return sum(Image.open(frame).convert("L").get_flattened_data()) / (90 * 160)


def pixabay_video(query: str, used: set, out_dir: Path) -> Path:
    """Pixabay 무료 영상. 가로 영상이 대부분이라 가운데를 9:16 으로 잘라 쓴다.
    User-Agent 가 없으면 Cloudflare 가 403(1010)을 낸다."""
    ua = {"User-Agent": "Mozilla/5.0 (lee-blog clip)"}
    r = requests.get("https://pixabay.com/api/videos/",
                     params={"key": env("PIXABAY_API_KEY"), "q": query, "per_page": 30, "video_type": "film",
                             "safesearch": "true"}, headers=ua, timeout=30)
    r.raise_for_status()
    hits = [h for h in r.json().get("hits", []) if h["id"] not in used and h.get("duration", 0) >= 4
            and not BLOCK_TAGS.intersection(x.strip().lower() for x in h.get("tags", "").split(","))]
    # 세로 영상을 먼저, 그다음 가로
    hits.sort(key=lambda h: h["videos"]["medium"]["height"] < h["videos"]["medium"]["width"])
    for h in hits:
        v = h["videos"].get("large") or {}
        if not v.get("url") or v.get("height", 0) < 720:
            v = h["videos"]["medium"]
        if not v.get("url"):
            continue
        used.add(h["id"])
        path = _download(v["url"], out_dir / f"pixabay_{h['id']}.mp4", ua)
        if brightness(path) > 175:  # 흰 종이·흰 벽 위주 영상은 글씨가 묻힌다
            continue
        return path
    raise RuntimeError(f"Pixabay 에 맞는 영상이 없음: {query}")


def pixabay_by_id(vid: int, out_dir: Path) -> Path:
    """사람이 골라 둔 Pixabay 영상 번호로 받는다."""
    ua = {"User-Agent": "Mozilla/5.0 (lee-blog clip)"}
    r = requests.get("https://pixabay.com/api/videos/", params={"key": env("PIXABAY_API_KEY"), "id": vid},
                     headers=ua, timeout=30)
    r.raise_for_status()
    v = r.json()["hits"][0]["videos"]
    v = v["large"] if v.get("large", {}).get("url") else v["medium"]
    return _download(v["url"], out_dir / f"pixabay_{vid}.mp4", ua)


VISION_PROMPT = """세로 영상(9:16) 클립의 배경 영상을 고른다. 위 그림은 후보 {n}개의 미리보기(번호 0~{last})다.

[이 장면 자막] {subs}
[클립 제목] {title}

고르는 기준
- 자막의 뜻이나 비유와 어울리는 것. 사물·공간·손 위주.
- 사람 얼굴이 크게 나오는 것, 연출 티 나는 모델, 노출 있는 옷차림, CG·애니메이션·추상 그래픽은 고르지 않는다.
- 가운데를 세로로 잘라 쓰므로 주제가 가운데에 있는 것이 좋다.
맞는 게 없으면 pick 을 -1 로 하고, 더 나은 영어 검색어(2~4단어, 사물 위주)를 alt_query 에 쓴다.

JSON 하나만 출력: {{"pick": 번호, "alt_query": "", "reason": "한 줄"}}"""


def _candidates(query: str, used: set, k: int = 8) -> list:
    ua = {"User-Agent": "Mozilla/5.0 (lee-blog clip)"}
    r = requests.get("https://pixabay.com/api/videos/",
                     params={"key": env("PIXABAY_API_KEY"), "q": query, "per_page": 30, "video_type": "film",
                             "safesearch": "true"}, headers=ua, timeout=30)
    r.raise_for_status()
    return [h for h in r.json().get("hits", []) if h["id"] not in used and h.get("duration", 0) >= 4
            and not BLOCK_TAGS.intersection(x.strip().lower() for x in h.get("tags", "").split(","))][:k]


def _grid(hits: list) -> bytes:
    """후보 미리보기를 번호 붙인 한 장으로 묶는다 (Claude 에 그림 한 장으로 보낸다)."""
    import io
    ua = {"User-Agent": "Mozilla/5.0 (lee-blog clip)"}
    cw, ch, cols = 320, 180, 4
    rows = (len(hits) + cols - 1) // cols
    sheet = Image.new("RGB", (cw * cols, (ch + 34) * rows), "white")
    d = ImageDraw.Draw(sheet)
    for i, h in enumerate(hits):
        x, y = (i % cols) * cw, (i // cols) * (ch + 34)
        try:
            th = requests.get(h["videos"]["tiny"]["thumbnail"], headers=ua, timeout=20).content
            sheet.paste(Image.open(io.BytesIO(th)).convert("RGB").resize((cw - 6, ch)), (x + 3, y))
        except Exception:  # noqa: BLE001
            pass
        d.text((x + 8, y + ch + 4), str(i), font=font(26), fill=(0, 0, 0))
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def vision_picker(client, model: str, title: list):
    """Claude 가 후보 미리보기를 보고 장면마다 영상을 고르는 함수를 만든다 (clip.build 의 picker)."""
    import base64

    def pick(sc: dict, used: set, out_dir: Path) -> Path:
        query = sc["query"]
        for _ in range(2):
            hits = _candidates(query, used)
            if len(hits) >= 2:
                img = base64.b64encode(_grid(hits)).decode()
                text = VISION_PROMPT.format(n=len(hits), last=len(hits) - 1, title=" ".join(title),
                                            subs=" / ".join(s.replace("\n", " ") for s in sc.get("subs", [sc["say"]])))
                try:
                    resp = client.messages.create(model=model, max_tokens=4000, messages=[{"role": "user", "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img}},
                        {"type": "text", "text": text}]}])
                    raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
                    ans = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
                    k = int(ans.get("pick", -1))
                    if 0 <= k < len(hits):
                        print(f"    영상 선택: {query} → {hits[k]['id']} ({ans.get('reason', '')})")
                        used.add(hits[k]["id"])
                        return pixabay_by_id(hits[k]["id"], out_dir)
                    query = ans.get("alt_query") or query
                    print(f"    맞는 영상 없음 → 다시 검색: {query}")
                    continue
                except Exception as exc:  # noqa: BLE001
                    print(f"    [경고] 영상 선택 실패, 검색 순서대로 씀 ({type(exc).__name__}: {exc})")
            break
        return stock_video(query, used, out_dir)

    return pick


def stock_video(query: str, used: set, out_dir: Path) -> Path:
    if env("PIXABAY_API_KEY"):
        return pixabay_video(query, used, out_dir)
    return pexels_video(query, used, out_dir)


def pexels_video(query: str, used: set, out_dir: Path) -> Path:
    r = requests.get("https://api.pexels.com/videos/search",
                     params={"query": query, "orientation": "portrait", "per_page": 10},
                     headers={"Authorization": env("PEXELS_API_KEY")}, timeout=30)
    r.raise_for_status()
    for v in r.json().get("videos", []):
        if v["id"] in used or v.get("duration", 0) < 4:
            continue
        files = [f for f in v["video_files"]
                 if f.get("height") and f.get("width") and f["height"] > f["width"] and f["height"] >= 1280]
        if not files:
            continue
        f = min(files, key=lambda x: x["height"])
        used.add(v["id"])
        return _download(f["link"], out_dir / f"pexels_{v['id']}.mp4")
    raise RuntimeError(f"Pexels 에 맞는 세로 영상이 없음: {query}")


# ---------- 자막 ----------
# 줄 맨 앞에 오면 어색한 의존 명사·보조 용언 (앞 낱말에 붙여 둔다)
_BOUND = ("수", "것", "게", "거", "줄", "때", "데", "뿐", "만큼", "듯", "적", "있다", "없다", "한다", "된다", "본다")


def _balanced_break(words: list) -> str:
    """두 줄 중 길이가 가장 비슷한 자리에서 나누되, 줄 머리에 _BOUND 가 오지 않게 한다."""
    best, best_gap = None, 10 ** 9
    for k in range(1, len(words)):
        if words[k].startswith(_BOUND):
            continue
        a, b = " ".join(words[:k]), " ".join(words[k:])
        gap = abs(len(a) - len(b))
        if gap < best_gap:
            best, best_gap = f"{a}\n{b}", gap
    return best or " ".join(words)


def chunks(text: str, line: int = 13) -> list:
    """자막 화면 단위로 나눈다. 쉼표·마침표로 의미 덩어리를 자르고,
    한 줄(line 자)을 넘으면 두 줄로 나눈다. 두 줄로도 넘치면 덩어리를 반으로 쪼갠다."""
    out = []
    for p in (x.strip().rstrip(",.") for x in re.split(r"(?<=[,.?!])\s+", text) if x.strip()):
        words = p.split()
        if len(p) <= line:
            out.append(p)
        elif len(p) <= line * 2:
            out.append(_balanced_break(words))
        else:
            half = len(words) // 2
            out += chunks(" ".join(words[:half]) + ",", line) + chunks(" ".join(words[half:]), line)
    return out


def font(size, path=None):
    return ImageFont.truetype(str(path or FONT), size)


def shadow_text(img, xy, text, f, fill, anchor="la", blur=10, alpha=170):
    """테두리 없이 부드러운 그림자만 깐다 (굵은 검은 테두리는 AI 티가 나서 쓰지 않는다)."""
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0] + 3, xy[1] + 5), text, font=f, fill=(0, 0, 0, alpha), anchor=anchor)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(img).text(xy, text, font=f, fill=fill, anchor=anchor)


def subtitle(img, y, text, f, em=()):
    """가운데 정렬 자막. em 에 든 낱말은 강조색."""
    d = ImageDraw.Draw(img)
    segs, rest = [], text
    for e in em:
        if e in rest:
            a, b = rest.split(e, 1)
            segs += [(a, WHITE), (e, ACCENT)]
            rest = b
    segs.append((rest, WHITE))
    x = (W - sum(d.textlength(s, font=f) for s, _ in segs)) / 2
    for s, c in segs:
        shadow_text(img, (x, y), s, f, c, blur=8, alpha=190)
        x += d.textlength(s, font=f)


def title_block(img, title, x=80, y=230, size=104):
    """에세이 톤 제목: 명조, 왼쪽 정렬, 마지막 줄만 강조색 (2026-10-20 사용자 선택 A안)."""
    f = font(size, TITLE_FONT)
    for k, line in enumerate(title):
        shadow_text(img, (x, y + k * int(size * 1.25)), line, f,
                    ACCENT if k == len(title) - 1 else WHITE)


def _shade(img, y0, y1, peak, top_dark=True):
    """y0~y1 구간에 위(또는 가운데)가 진하고 끝으로 갈수록 투명한 그늘을 깐다."""
    d = ImageDraw.Draw(img)
    for y in range(y0, y1):
        r = (y - y0) / (y1 - y0)
        a = peak * (1 - r) if top_dark else peak * (1 - abs(r - 0.5) * 2)
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(a)))


def _fit(d, lines, size, path, max_w=W - 140, floor=50):
    while max(d.textlength(x, font=font(size, path)) for x in lines) > max_w and size > floor:
        size -= 4
    return font(size, path), size


def _lines_left(img, x, y, lines, f, size, em, gap=1.4):
    d = ImageDraw.Draw(img)
    for k, line in enumerate(lines):
        cx, rest, segs = x, line, []
        for e in em:
            if e in rest:
                a, b = rest.split(e, 1)
                segs += [(a, WHITE), (e, ACCENT)]
                rest = b
        segs.append((rest, WHITE))
        for s, c in segs:
            shadow_text(img, (cx, y + k * int(size * gap)), s, f, c, blur=8, alpha=190)
            cx += d.textlength(s, font=f)


# 화면 구도 (2026-10-20 사용자: "텍스트 구도가 단조롭고 리듬감이 없다")
#   intro : 첫 화면. 큰 명조 제목 + 아래 자막
#   base  : 아래 가운데 자막
#   left  : 왼쪽 아래 정렬 자막 (조금 크게)
#   quote : 인용 대사. 화면 가운데 큰 명조 + 큰 따옴표
#   punch : 강조어 하나를 아주 크게, 나머지는 작게
LAYOUTS = ("intro", "base", "left", "quote", "punch")


def auto_layouts(scenes: list) -> list:
    """장면·자막마다 구도를 고른다. 같은 구도가 연달아 나오지 않게 섞는다."""
    out, prev, plain = [], None, 0
    for i, sc in enumerate(scenes):
        subs = sc.get("subs") or chunks(sc["say"])
        lays = []
        for k, s in enumerate(subs):
            want = (sc.get("layouts") or [None] * len(subs))[k] if k < len(sc.get("layouts") or []) else None
            if want in LAYOUTS:
                lay = want
            elif i == 0 and k == 0:
                lay = "intro"
            elif s.lstrip().startswith(("“", '"')) and prev != "quote":
                lay = "quote"
            elif (prev not in ("punch", "intro") and any(e in s and len(e) <= 7 for e in sc.get("em", []))
                  and len(s.replace("\n", "")) <= 22 and plain >= 1):
                lay = "punch"
            else:
                lay = ("base", "left")[plain % 2]
                plain += 1
            lays.append(lay)
            prev = lay
            if lay in ("quote", "punch"):
                plain = 1
        out.append(lays)
    return out


def layer_static(title, layout, path: Path):
    """움직이지 않는 층: 그늘 + 제목 (첫 화면은 크게, 나머지는 위쪽 작은 한 줄)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if layout == "intro":
        _shade(img, 300, 1500, 170, top_dark=False)
        title_block(img, title, y=560, size=118)
    elif layout == "quote":
        _shade(img, 450, 1350, 150, top_dark=False)
    else:
        _shade(img, 0, 420, 140)
        shadow_text(img, (80, 160), " ".join(t.rstrip(",") for t in title), font(46, TITLE_FONT),
                    (245, 238, 228), blur=6, alpha=160)
        if layout == "punch":
            _shade(img, 650, 1400, 140, top_dark=False)
        else:
            _shade(img, 1050, 1450, 130, top_dark=False)
    img.save(path)


def layer_text(sub, em, layout, path: Path):
    """움직이는 층: 자막. 구도마다 자리·크기·글꼴이 다르다."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lines = sub.split("\n")
    em = [e for e in em if e in sub]
    if layout == "quote":
        f, size = _fit(d, [x.replace("“", "").replace("”", "") for x in lines], 82, TITLE_FONT)
        shadow_text(img, (80, 640), "“", font(220, TITLE_FONT), ACCENT + (255,), blur=6, alpha=120)
        y0 = 860
        for k, x in enumerate(lines):
            x = x.replace("“", "").replace("”", "")
            shadow_text(img, (80, y0 + k * int(size * 1.45)), x, f, WHITE, blur=8, alpha=190)
    elif layout == "punch" and em:
        word = next(e for e in em)
        big, bsize = _fit(d, [word], 170, TITLE_FONT, floor=110)
        small, ssize = _fit(d, lines, 58, SUB_FONT)
        rest = [x for x in lines]
        y = 780
        _lines_left(img, 80, y, rest, small, ssize, [])
        shadow_text(img, (76, y + len(rest) * int(ssize * 1.4) + 30), word, big, ACCENT, blur=10, alpha=180)
    elif layout == "left" or layout == "intro":
        f, size = _fit(d, lines, 76 if layout == "left" else 66, SUB_FONT)
        y = 1170 if layout == "left" else 1240
        _lines_left(img, 80, y - (len(lines) - 1) * int(size * 1.4) // 2, lines, f, size, em)
    else:
        f, size = _fit(d, lines, 70, SUB_FONT)
        gap = int(size * 1.4)
        y0 = 1240 - (len(lines) - 1) * gap // 2
        for k, x in enumerate(lines):
            subtitle(img, y0 + k * gap, x, f, [e for e in em if e in x])
    img.save(path)


def overlay(title, sub, em, path: Path, layout: str = "base"):
    """정지 화면 한 장 (미리보기·표지 시험용). 영상은 layer_static + layer_text 를 따로 겹친다."""
    a, b = path.with_suffix(".s.png"), path.with_suffix(".t.png")
    layer_static(title, layout, a)
    layer_text(sub, em, layout, b)
    img = Image.open(a)
    img.alpha_composite(Image.open(b))
    img.save(path)
    a.unlink()
    b.unlink()


def end_card(title, line, path: Path, style: str = "search"):
    img = Image.new("RGBA", (W, H), (34, 29, 25, 255))
    title_block(img, title, y=430, size=96)
    d = ImageDraw.Draw(img)
    d.text((80, 900), line, font=font(56, SUB_FONT), fill=(225, 218, 208))
    if style == "link":
        d.rounded_rectangle([80, 1010, W - 80, 1150], radius=70, fill=(255, 255, 255))
        d.text((W / 2, 1080), "블로그 글에서 전체 보기  →", font=font(62, SUB_FONT),
               fill=(25, 25, 25), anchor="mm")
        d.text((80, 1220), "역삼동이선생 · 슬기로운 직장생활", font=font(50, SUB_FONT), fill=(170, 162, 150))
        img.convert("RGB").save(path)
        return
    # 네이버 검색창
    d.rounded_rectangle([80, 1010, W - 80, 1150], radius=70, fill=(255, 255, 255), outline=NAVER, width=5)
    d.text((140, 1080), "N", font=font(72, SUB_FONT), fill=NAVER, anchor="lm")
    d.text((240, 1080), "역삼동이선생", font=font(66, SUB_FONT), fill=(25, 25, 25), anchor="lm")
    cx, cy = W - 165, 1080
    d.ellipse([cx - 30, cy - 34, cx + 22, cy + 18], outline=NAVER, width=8)
    d.line([cx + 14, cy + 10, cx + 40, cy + 36], fill=NAVER, width=9)
    d.text((80, 1220), "검색해서 블로그 글 전체 보기", font=font(50, SUB_FONT), fill=(170, 162, 150))
    img.convert("RGB").save(path)


def cover(title, clip: Path, path: Path):
    """표지 이미지. 인스타 프로필 격자는 세로 영상의 가운데 3:4(1080x1440)만 보여 주므로
    제목을 화면 가운데(위아래 240px 바깥은 비움)에 크게 둔다. 네이버 클립 표지로도 쓴다."""
    frame = path.with_suffix(".png")
    run(["-ss", "1", "-i", str(clip), "-vf",
         f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},eq=brightness=0.03",
         "-frames:v", "1", str(frame)])
    img = Image.open(frame).convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _shade(shade, 420, 1500, 165, top_dark=False)
    img.alpha_composite(shade)
    title_block(img, title, y=700, size=118)
    ImageDraw.Draw(img).text((84, 1205), "역삼동이선생", font=font(46, SUB_FONT), fill=(235, 228, 218))
    img.convert("RGB").save(path, quality=92)
    frame.unlink()


# ---------- 조립 ----------
def build(job_path: Path, picker=None, out: Path = None):
    job = json.loads(job_path.read_text(encoding="utf-8"))
    out = out or job_path.parent / job_path.stem
    work = out / "work"
    foot = job_path.parent / "footage"
    for p in (out, work, foot):
        p.mkdir(parents=True, exist_ok=True)

    used, segs, auds = set(), [], []
    layouts = auto_layouts(job["scenes"])
    first_clip = None
    n = 0
    for i, sc in enumerate(job["scenes"]):
        mp3 = work / f"say{i:02d}_{hashlib.md5((sc['say'] + job['rate']).encode()).hexdigest()[:8]}.mp3"
        dur = tts(sc["say"], job["voice"], job["rate"], mp3) + 0.25
        wav = work / f"say{i:02d}.wav"
        run(["-i", str(mp3), "-af", f"apad=whole_dur={dur:.3f}", "-ar", "44100", "-ac", "2", str(wav)])
        auds.append(wav)

        if sc.get("end"):
            png = work / "end.png"
            end_card(job["title"], job.get("end_line", "전문은 블로그에서"), png, job.get("end_style", "search"))
            seg = work / f"seg{n:03d}.mp4"
            run(["-loop", "1", "-t", f"{dur + 0.6:.3f}", "-i", str(png),
                 "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "20", str(seg)])
            segs.append(seg)
            auds[-1] = wav  # 마지막 장면은 음성 뒤 1.2초 여유 (영상만 길고 음성은 끝)
            n += 1
            continue

        used.update(job.get("avoid", []))  # 사람이 보고 뺀 영상
        if sc.get("pixabay_id"):
            clip = pixabay_by_id(sc["pixabay_id"], foot)
        elif picker:
            clip = picker(sc, used, foot)
        else:
            clip = stock_video(sc["query"], used, foot)
        print(f"  장면 {i + 1}: {clip.name}  ({sc['query']})")
        first_clip = first_clip or clip
        # subs 가 있으면 사람이 끊어 둔 대로 쓴다 ("\n" 은 줄바꿈)
        pieces = sc.get("subs") or chunks(sc["say"])
        lengths = [len(p.replace("\n", "")) for p in pieces]
        offset = 0.0
        for k, piece in enumerate(pieces):
            d = dur * lengths[k] / sum(lengths)
            lay = layouts[i][k]
            st, tx = work / f"st{n:03d}.png", work / f"tx{n:03d}.png"
            layer_static(job["title"], lay, st)
            layer_text(piece, sc.get("em", []), lay, tx)
            seg = work / f"seg{n:03d}.mp4"
            # 자막은 0.35초 동안 살짝 떠오르며 나타난다 (화면마다 리듬이 생기게)
            rise = "if(lt(t,0.35),36*(1-t/0.35),0)"
            run(["-stream_loop", "-1", "-ss", f"{offset:.3f}", "-t", f"{d:.3f}", "-i", str(clip),
                 "-i", str(st), "-i", str(tx), "-filter_complex",
                 # 이미지는 한 장만 넣고 필터 안에서 반복한다 (-loop 1 입력은 버퍼 오류가 났다)
                 f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                 f"eq=brightness=0.03:saturation=1.03,fps={FPS},setsar=1[b];"
                 f"[2:v]format=rgba,loop=loop=-1:size=1:start=0,setpts=N/{FPS}/TB,"
                 f"fade=t=in:st=0:d=0.35:alpha=1[t];"
                 f"[b][1:v]overlay=0:0[s];[s][t]overlay=x=0:y='{rise}',format=yuv420p",
                 "-t", f"{d:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(seg)])
            segs.append(seg)
            offset += d
            n += 1

    # 영상·음성 이어 붙이기
    (work / "v.txt").write_text("".join(f"file '{s.resolve().as_posix()}'\n" for s in segs), encoding="utf-8")
    (work / "a.txt").write_text("".join(f"file '{a.resolve().as_posix()}'\n" for a in auds), encoding="utf-8")
    run(["-f", "concat", "-safe", "0", "-i", str(work / "v.txt"), "-c", "copy", str(work / "v.mp4")])
    run(["-f", "concat", "-safe", "0", "-i", str(work / "a.txt"), "-c:a", "pcm_s16le", str(work / "a.wav")])
    final = out / f"{job_path.stem}_clip.mp4"
    run(["-i", str(work / "v.mp4"), "-i", str(work / "a.wav"), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(final)])
    # 캡션: 네이버 클립용과 인스타 릴스용을 따로 저장한다
    (out / "caption_naver.txt").write_text(job["caption"], encoding="utf-8")
    if job.get("caption_instagram"):
        (out / "caption_instagram.txt").write_text(job["caption_instagram"], encoding="utf-8")
    if first_clip:
        cover(job["title"], first_clip, out / "cover.jpg")
    print(f"[ok] {final} ({duration(final):.1f}초)")
    return final


if __name__ == "__main__":
    build(Path(sys.argv[1]))
