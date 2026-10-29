# -*- coding: utf-8 -*-
"""사진 클립 — 후킹 리스트형(hook) / 현장형(place) (2026-10-29).

사용자가 보여 준 참고 클립을 옮겼다.
  hook : 패션 후킹 클립(버켄스탁·롱부츠). 사진을 꽉 채우고, 위에 채널 이름 + 색 태그(01 / 말투) +
         두 줄 헤드라인(흰색 + 강조색), 아래에 작은 설명 박스와 영문 꼬리표. 장면이 빨리 넘어간다.
  place: 스카이밸리CC 클립. 사진 위 가운데 담백한 두 줄 자막(강조어만 색), 위 왼쪽 위치 태그,
         끝은 이름·주소 같은 정보 카드.
둘 다 내레이션 없음 (2026-10-29 사용자: "음성 빼줘, 어색해"). 음원은 클립 앱에서 고른다.
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from clip import FF

ROOT = Path(__file__).parent
FONT = {w: str(ROOT / "fonts" / f"Pretendard-{w}.otf") for w in ("ExtraBold", "Bold", "SemiBold", "Medium")}
W, H, FPS = 1080, 1920, 30
X0, X1 = 64, W - 150          # 오른쪽은 클립 버튼 자리라 비운다
WHITE, DARK = (255, 255, 255), (20, 20, 22)
# 사진 위에서 잘 보이는 밝은 강조색
ACCENTS = {"lime": (212, 245, 90), "amber": (255, 204, 112), "coral": (255, 150, 128),
           "sky": (140, 202, 255), "mint": (130, 232, 196), "pink": (255, 160, 200)}
XFADE = 6                     # 장면 사이 겹침 프레임 수


def F(w, s):
    return ImageFont.truetype(FONT[w], s)


def fit(text, w, size, max_w=X1 - X0, floor=34):
    while size > floor and F(w, size).getlength(text) > max_w:
        size -= 3
    return size


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def cover_crop(src: Image.Image, w: int, h: int) -> Image.Image:
    s = max(w / src.width, h / src.height)
    src = src.resize((round(src.width * s), round(src.height * s)), Image.LANCZOS)
    x, y = (src.width - w) // 2, (src.height - h) // 2
    return src.crop((x, y, x + w, y + h))


def prep(path) -> Image.Image:
    """천천히 움직일 여유를 두고 1.14배로 맞춰 둔다. 살짝 밝고 선명하게."""
    img = cover_crop(Image.open(path).convert("RGB"), int(W * 1.14), int(H * 1.14))
    return ImageEnhance.Contrast(ImageEnhance.Brightness(img).enhance(1.02)).enhance(1.04)


MOVES = ["in", "left", "out", "up", "right", "in"]


def frame(bg: Image.Image, move: str, p: float) -> Image.Image:
    """p(0~1) 진행에 따라 확대·이동한 화면 한 장."""
    bw, bh = bg.size
    p = ease(p * 0.9 + 0.05)
    if move in ("in", "out"):
        z = 1 + 0.12 * (p if move == "in" else 1 - p)   # 1 → 1.12배 확대
        cw, ch = bw / 1.14 * (1.14 / z), bh / 1.14 * (1.14 / z)
        x, y = (bw - cw) / 2, (bh - ch) / 2
    else:
        cw, ch = bw / 1.14, bh / 1.14
        x, y = (bw - cw) / 2, (bh - ch) / 2
        dx, dy = (bw - cw) / 2 * 0.9, (bh - ch) / 2 * 0.9
        x += {"left": dx * (1 - 2 * p), "right": dx * (2 * p - 1)}.get(move, 0)
        y += {"up": dy * (1 - 2 * p)}.get(move, 0)
    return bg.crop((int(x), int(y), int(x + cw), int(y + ch))).resize((W, H), Image.BILINEAR)


def gradient(y0, y1, a0, a1) -> Image.Image:
    g = Image.new("L", (1, H), 0)
    for y in range(y0, y1):
        g.putpixel((0, y), int(a0 + (a1 - a0) * (y - y0) / max(y1 - y0, 1)))
    if a1 > 0 and y1 < H:
        for y in range(y1, H):
            g.putpixel((0, y), a1)
    return Image.merge("RGBA", (Image.new("L", (W, H), 0),) * 3 + (g.resize((W, H)),))


def shadowed(layer: Image.Image, blur=12, alpha=0.75) -> Image.Image:
    """글자 레이어 아래 부드러운 그림자 (굵은 테두리는 AI 티가 나서 쓰지 않는다)."""
    a = layer.getchannel("A").filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * alpha))
    sh = Image.merge("RGBA", (Image.new("L", layer.size, 0),) * 3 + (a,))
    sh.alpha_composite(layer)
    return sh


def faded(layer: Image.Image, a: float, dy: int = 0) -> Image.Image:
    if a >= 1 and not dy:
        return layer
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    lay = layer.copy()
    lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a)))
    out.paste(lay, (0, dy), lay)
    return out


def text_em(d, xy, text, f, em, color, anchor="la"):
    """한 줄을 쓰되 em 부분만 강조색."""
    x, y = xy
    if anchor == "ma":
        x -= d.textlength(text, font=f) / 2
    if em and em in text:
        a, b = text.split(em, 1)
        d.text((x, y), a, font=f, fill=WHITE)
        x += d.textlength(a, font=f)
        d.text((x, y), em, font=f, fill=color)
        d.text((x + d.textlength(em, font=f), y), b, font=f, fill=WHITE)
    else:
        d.text((x, y), text, font=f, fill=WHITE)


# ---------- 후킹 리스트형 ----------
def hook_layers(job, sc, acc):
    """(먼저 뜨는 위쪽 레이어, 조금 뒤 뜨는 아래 레이어)"""
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(top)
    d.text((X0, 96), job.get("channel", "역삼동 이선생"), font=F("ExtraBold", 34), fill=WHITE)
    tag = sc.get("tag", "")
    y = 160
    if tag:
        f = F("ExtraBold", 30)
        tw = d.textlength(tag, font=f)
        d.rounded_rectangle([X0, y, X0 + tw + 36, y + 54], radius=8, fill=acc)
        d.text((X0 + 18, y + 10), tag, font=f, fill=DARK)
        y += 84
    lines = sc["head"][:2]
    size = min(fit(x, "ExtraBold", 84) for x in lines)
    for k, line in enumerate(lines):
        d.text((X0, y), line, font=F("ExtraBold", size), fill=WHITE if k == 0 else acc)
        y += int(size * 1.24)
    bot = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(bot)
    if sc.get("chip"):
        size = fit(sc["chip"], "Bold", 44, X1 - X0 - 48)
        f = F("Bold", size)
        tw = d.textlength(sc["chip"], font=f)
        d.rounded_rectangle([X0, 1500, X0 + tw + 48, 1500 + size + 40], radius=10, fill=(16, 16, 18, 200))
        d.text((X0 + 24, 1500 + 18), sc["chip"], font=f, fill=WHITE)
    if job.get("label"):
        d.text((X0, 1640), job["label"], font=F("SemiBold", 28), fill=(255, 255, 255, 220))
    return shadowed(top), bot


def hook_end(job, bg, acc):
    """마지막 화면: 첫 사진을 흐리고 어둡게 깔고 마무리 두 줄 + 블로그 버튼 + 질문."""
    img = ImageEnhance.Brightness(cover_crop(bg, W, H).filter(ImageFilter.GaussianBlur(26))).enhance(0.45)
    img = img.convert("RGBA")
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    end = job["end"]
    lines = end["lines"][:3]
    size = min(fit(x, "ExtraBold", 92) for x in lines)
    y = 640
    for k, line in enumerate(lines):
        d.text((X0 + 26, y), line, font=F("ExtraBold", size), fill=acc if k == len(lines) - 1 else WHITE)
        y += int(size * 1.3)
    y += 60
    btn = end.get("button", "블로그 글에서 전체 보기")
    d.rounded_rectangle([X0 + 26, y, X1, y + 130], radius=65, fill=acc)
    d.text(((X0 + 26 + X1) / 2 - d.textlength(btn, font=F("Bold", 50)) / 2, y + 36), btn,
           font=F("Bold", 50), fill=DARK)
    if end.get("question"):
        d.text((X0 + 26, y + 220), end["question"], font=F("SemiBold", fit(end["question"], "SemiBold", 52)),
               fill=(235, 235, 235))
    return img, lay


# ---------- 현장형 ----------
def place_layers(job, sc, acc, first):
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(top)
    pl = job["place"]
    if first:  # 첫 화면: 작은 머리말 + 큰 이름 + 짧은 밑줄
        d.text((X0, 250), pl.get("kicker", ""), font=F("SemiBold", 40), fill=WHITE)
        size = fit(pl["name"], "ExtraBold", 120)
        d.text((X0, 306), pl["name"], font=F("ExtraBold", size), fill=WHITE)
        d.rectangle([X0 + 4, 306 + size * 1.32, X0 + 64, 306 + size * 1.32 + 7], fill=acc)
    else:
        d.ellipse([X0, 110, X0 + 14, 124], fill=acc)
        d.text((X0 + 30, 98), pl.get("tag", pl["name"]), font=F("SemiBold", 32), fill=WHITE)
    bot = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(bot)
    lines = sc["sub"].split("\n")[:2]
    size = min(fit(x, "SemiBold", 62, W - 200) for x in lines)
    y = 1180 - len(lines) * size * 0.7
    for line in lines:
        text_em(d, (W / 2, y), line, F("SemiBold", size), sc.get("em", ""), acc, anchor="ma")
        y += int(size * 1.45)
    return shadowed(top), shadowed(bot, blur=10, alpha=0.95)


def place_end(job, bg, acc):
    img = ImageEnhance.Brightness(cover_crop(bg, W, H).filter(ImageFilter.GaussianBlur(28))).enhance(0.42)
    img = img.convert("RGBA")
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    pl, cx = job["place"], W / 2

    def center(y, text, f, fill):
        d.text((cx - d.textlength(text, font=f) / 2, y), text, font=f, fill=fill)

    y = 520
    center(y, pl.get("kicker", ""), F("Medium", 44), acc)
    y += 84
    center(y, pl["name"], F("ExtraBold", fit(pl["name"], "ExtraBold", 108, W - 160)), WHITE)
    y += 176
    d.line([(cx - 60, y), (cx + 60, y)], fill=acc, width=4)
    y += 64
    for k, v in pl.get("info", [])[:3]:
        center(y, k, F("Medium", 38), acc)
        center(y + 54, v, F("Bold", fit(v, "Bold", 46, W - 160)), WHITE)
        y += 156
    btn = job["end"].get("button", "블로그 글에서 전체 보기")
    y += 30
    bw = d.textlength(btn, font=F("Bold", 46)) + 120
    d.rounded_rectangle([cx - bw / 2, y, cx + bw / 2, y + 118], radius=59, fill=(255, 255, 255, 235))
    center(y + 32, btn, F("Bold", 46), DARK)
    return img, lay


# ---------- 조립 ----------
def scene_dur(job, sc):
    if job["style"] == "hook":
        n = len("".join(sc["head"])) + len(sc.get("chip", ""))
        return min(max(1.6 + n / 11, 2.6), 4.2)
    n = len(sc["sub"].replace("\n", ""))
    return min(max(1.4 + n / 9, 3.0), 4.6)


def render(job, photos: list, out: Path) -> float:
    """photos: 장면마다 사진 경로 (모자라면 돌려 쓴다)."""
    acc = ACCENTS.get(job.get("accent", "lime"), ACCENTS["lime"])
    style = job["style"]
    top_shade = gradient(0, 760, 170, 0) if style == "hook" else gradient(0, 420, 120, 0)
    # 현장형 자막은 밝은 하늘·잔디 위에 얹히므로 자막 자리부터 넉넉히 어둡게
    bot_shade = gradient(780, 1320, 0, 175) if style == "place" else gradient(1300, 1920, 0, 150)
    shade = Image.alpha_composite(top_shade, bot_shade)
    p = subprocess.Popen([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
                          "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    total, prev = 0.0, None
    for i, sc in enumerate(job["scenes"]):
        bg = prep(photos[i % len(photos)])
        if style == "hook":
            top, bot = hook_layers(job, sc, acc)
        else:
            top, bot = place_layers(job, sc, acc, i == 0)
        dur = sc.get("dur") or scene_dur(job, sc)
        n = round(dur * FPS)
        for k in range(n):
            t = k / FPS
            img = frame(bg, MOVES[i % len(MOVES)], k / n).convert("RGBA")
            img.alpha_composite(shade)
            img.alpha_composite(faded(top, ease(t / 0.35), int(24 * (1 - ease(t / 0.35)))))
            img.alpha_composite(faded(bot, ease((t - 0.35) / 0.35), int(30 * (1 - ease((t - 0.35) / 0.35)))))
            img = img.convert("RGB")
            last = img
            if k < XFADE and prev is not None:
                img = Image.blend(prev, img, (k + 1) / (XFADE + 1))
            p.stdin.write(img.tobytes())
        prev, total = last, total + dur
    # 끝 화면
    first = Image.open(photos[0]).convert("RGB")
    base, lay = (hook_end if style == "hook" else place_end)(job, first, acc)
    n = round(4.2 * FPS)
    for k in range(n):
        img = base.copy()
        img.alpha_composite(faded(lay, ease(k / FPS / 0.4), int(30 * (1 - ease(k / FPS / 0.4)))))
        img = img.convert("RGB")
        if k < XFADE:
            img = Image.blend(prev, img, (k + 1) / (XFADE + 1))
        p.stdin.write(img.tobytes())
    p.stdin.close()
    p.wait()
    return total + 4.2
