# -*- coding: utf-8 -*-
"""정보형 클립 견본 (2026-10-23).

사용자 피드백: 지금 클립은 너무 감성적이라 무슨 메시지인지 모르겠다 → 답을 클립 안에서 주고,
더 자세한 건 블로그로. 화면이 단조롭지 않게 자막 타이핑, 표 정리 같은 움직임을 넣는다.

화면: 밝은 종이색 바탕 + 굵은 고딕(Pretendard) + 이선생 amber 강조. 내레이션 없음(음원은 앱에서).
장면 종류: hook(큰 글자 타이핑 + 형광펜) / cards(번호 카드) / table(표, 줄마다 등장) / list(체크) / end
사용: python info_clip.py <출력.mp4>
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from clip import FF  # noqa: E402

ROOT = Path(__file__).parent
FONT = {w: str(ROOT / "fonts" / f"Pretendard-{w}.otf") for w in ("ExtraBold", "Bold", "SemiBold", "Medium")}
W, H, FPS = 1080, 1920, 30
PAPER, INK, SUBINK, LINE = (245, 241, 234), (28, 28, 30), (110, 106, 100), (222, 215, 204)
AMBER, AMBER_SOFT, CARD = (226, 150, 40), (255, 214, 140), (255, 255, 255)
X0, X1 = 90, W - 150          # 오른쪽은 클립 버튼 자리라 비운다
CPS = 16                      # 타이핑 속도 (글자/초)

# 글마다 색을 바꾼다 (2026-10-29 사용자: "글에 따라서 스타일이 자유자재로 변형되어야 해")
ACCENTS = {"amber": ((226, 150, 40), (255, 214, 140)), "coral": ((226, 92, 70), (255, 200, 186)),
           "teal": ((18, 140, 130), (172, 228, 218)), "blue": ((50, 104, 220), (192, 212, 255)),
           "green": ((40, 150, 80), (190, 232, 196))}
THEMES = {"paper": ((245, 241, 234), (28, 28, 30), (110, 106, 100), (222, 215, 204), (255, 255, 255)),
          "night": ((24, 25, 30), (244, 240, 232), (158, 154, 148), (62, 63, 70), (38, 39, 46))}


def set_theme(accent="amber", theme="paper"):
    global AMBER, AMBER_SOFT, PAPER, INK, SUBINK, LINE, CARD
    AMBER, AMBER_SOFT = ACCENTS.get(accent, ACCENTS["amber"])
    PAPER, INK, SUBINK, LINE, CARD = THEMES.get(theme, THEMES["paper"])
    if theme == "night":  # 어두운 바탕에선 형광펜을 진한 색으로, 강조 글자는 밝은 색으로
        AMBER, AMBER_SOFT = AMBER_SOFT, tuple(int(c * 0.55) for c in AMBER)


def F(w, s):
    return ImageFont.truetype(FONT[w], s)


def fit(text, w, size, max_w=X1 - X0, floor=36):
    """max_w 안에 들어가는 가장 큰 글꼴 (긴 문장이 화면 밖으로 나가지 않게)."""
    while size > floor and F(w, size).getlength(text) > max_w:
        size -= 4
    return size


def auto_dur(sc):
    """타이핑·등장 시간 + 읽을 시간으로 장면 길이를 정한다."""
    typ = lambda xs: sum(len(x) for x in xs) / CPS + 0.12 * len(xs)  # noqa: E731
    k = sc["type"]
    if k == "photo":
        return 2.6
    if k == "hook":
        return round(typ(sc["lines"]) + (1.0 if sc.get("sub") else 0) + 1.6, 1)
    if k == "quote":
        return round(typ(sc["lines"]) + 2.2, 1)
    if k == "cards":
        return round(len(sc["title"]) / CPS + 0.7 * len(sc["items"]) + 2.6, 1)
    if k == "table":
        return round(len(sc["title"]) / CPS + 0.45 * len(sc["rows"]) + 2.8, 1)
    if k == "list":
        return round(len(sc["title"]) / CPS + typ(sc["items"]) + 0.25 * len(sc["items"]) + 1.8, 1)
    return round(typ(sc["lines"]) + 3.0, 1)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def typed(text, t, start=0.0):
    """start 초부터 타이핑. 보여 줄 글자 수만큼 자른 문자열과 다 쳤는지."""
    n = int(max(t - start, 0) * CPS)
    return text[:n], n >= len(text)


def cursor(d, x, y, size, t):
    if int(t * 2.4) % 2 == 0:
        d.rectangle([x + 6, y + size * 0.12, x + 12, y + size * 1.08], fill=AMBER)


def backdrop(path):
    """글 사진을 흐리게 깔고 종이색을 덮어 보고서 같은 딱딱함을 누그러뜨린다 (2026-10-23 사용자 요청).
    조금 크게 만들어 두고 프레임마다 천천히 옮겨 잘라 쓴다."""
    if not path or not Path(path).exists():
        return None
    src = Image.open(path).convert("RGB")
    bw, bh = int(W * 1.12), int(H * 1.12)
    s = max(bw / src.width, bh / src.height)
    src = src.resize((round(src.width * s), round(src.height * s)), Image.LANCZOS)
    src = src.crop(((src.width - bw) // 2, (src.height - bh) // 2, (src.width - bw) // 2 + bw,
                    (src.height - bh) // 2 + bh)).filter(ImageFilter.GaussianBlur(22))
    return Image.blend(src, Image.new("RGB", src.size, PAPER), 0.74)


def base(job, idx, t_total, bg=None):
    if bg is not None:  # 영상 전체에 걸쳐 오른쪽 위로 아주 천천히 흐른다
        dx, dy = (bg.width - W) * t_total, (bg.height - H) * (1 - t_total)
        img = bg.crop((int(dx), int(dy), int(dx) + W, int(dy) + H))
    else:
        img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    # 맨 위: 진행 막대 + 채널 이름
    d.rectangle([0, 0, W, 10], fill=LINE)
    d.rectangle([0, 0, int(W * t_total), 10], fill=AMBER)
    # 채널 이름은 넣지 않는다 (2026-10-29 사용자: 붙박이처럼 고정돼 부담스럽다)
    pg = f"{idx + 1} / {len(job['scenes'])}"
    d.text((X1 - d.textlength(pg, font=F("Medium", 32)), 152), pg, font=F("Medium", 32), fill=SUBINK)
    d.line([(X0, 214), (X1, 214)], fill=LINE, width=3)
    return img, d


def head(d, text, t, y=380):
    """장면 제목: 타이핑."""
    s, _ = typed(text, t)
    size = fit(text, "ExtraBold", 88)
    f = F("ExtraBold", size)
    d.text((X0, y), s, font=f, fill=INK)
    if len(s) < len(text):
        cursor(d, X0 + d.textlength(s, font=f), y, size, t)
    return y + 160


def appear(img, layer, t, start, dy=40):
    """layer 를 start 초부터 0.3초 동안 아래에서 올라오며 나타나게."""
    a = ease((t - start) / 0.3)
    if a <= 0:
        return
    lay = layer.copy()
    lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a)))
    img.paste(lay, (0, int(dy * (1 - a))), lay)


# ---------- 장면 ----------
def s_quote(img, d, sc, t):
    """에세이형 첫 장면: 실제 들은 말 한마디를 큰 따옴표와 함께 타이핑."""
    d.text((X0 - 6, 330), "“", font=F("ExtraBold", 260), fill=AMBER)
    f = F("Bold", min(fit(x, "Bold", 84) for x in sc["lines"]))
    y, start = 620, 0.3
    for line in sc["lines"]:
        s, done = typed(line, t, start)
        d.text((X0, y), s, font=f, fill=INK)
        if s and not done:
            cursor(d, X0 + d.textlength(s, font=f), y, 84, t)
        y += 125
        start += len(line) / CPS + 0.12
    a = ease((t - start - 0.2) / 0.4)
    if a > 0 and sc.get("who"):
        c = tuple(int(PAPER[i] + (SUBINK[i] - PAPER[i]) * a) for i in range(3))
        d.line([(X0, y + 50), (X0 + 60, y + 50)], fill=c, width=4)
        d.text((X0 + 84, y + 26), sc["who"], font=F("SemiBold", 48), fill=c)


def s_hook(img, d, sc, t):
    lines, em = sc["lines"], sc.get("em", "")
    size = min(sc.get("size", 172), *(fit(x, "ExtraBold", 172) for x in lines))
    f = F("ExtraBold", size)
    y, start = 500, 0.15
    for line in lines:
        s, done = typed(line, t, start)
        if em and em in line and done:  # 다 친 뒤 형광펜이 그어진다
            a = ease((t - start - len(line) / CPS) / 0.35)
            ex = X0 + d.textlength(line[:line.index(em)], font=f)
            ew = d.textlength(em, font=f)
            d.rectangle([ex - 8, y + size * 0.64, ex - 8 + (ew + 16) * a, y + size * 1.16], fill=AMBER_SOFT)
        d.text((X0, y), s, font=f, fill=INK)
        if s and not done:
            cursor(d, X0 + d.textlength(s, font=f), y, size, t)
        y += int(size * 1.25)
        start += len(line) / CPS + 0.1
    if sc.get("sub"):
        a = ease((t - start - 0.2) / 0.4)
        if a > 0:
            c = tuple(int(PAPER[i] + (SUBINK[i] - PAPER[i]) * a) for i in range(3))
            d.text((X0, y + 50), sc["sub"], font=F("SemiBold", 54), fill=c)


def s_cards(img, d, sc, t):
    y = head(d, sc["title"], t)
    t0 = len(sc["title"]) / CPS + 0.2
    for i, (big, small) in enumerate(sc["items"]):
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        ld.rounded_rectangle([X0, y, X1, y + 300], radius=30, fill=CARD, outline=LINE, width=3)
        ld.ellipse([X0 + 40, y + 90, X0 + 160, y + 210], fill=AMBER)
        num = str(i + 1)
        ld.text((X0 + 100 - ld.textlength(num, font=F("ExtraBold", 64)) / 2, y + 112), num,
                font=F("ExtraBold", 64), fill=CARD)
        ld.text((X0 + 200, y + 66), big, font=F("ExtraBold", fit(big, "ExtraBold", 72, X1 - X0 - 240)), fill=INK)
        ld.text((X0 + 202, y + 176), small, font=F("Medium", fit(small, "Medium", 46, X1 - X0 - 240)), fill=SUBINK)
        appear(img, lay, t, t0 + i * 0.7)
        y += 340
    if sc.get("note"):
        a = ease((t - t0 - len(sc["items"]) * 0.7 - 0.2) / 0.4)
        if a > 0:
            d.text((X0, y + 20), sc["note"], font=F("Medium", 42), fill=SUBINK)


def s_table(img, d, sc, t):
    y = head(d, sc["title"], t)
    t0 = len(sc["title"]) / CPS + 0.2
    n = len(sc["header"])  # 열 너비 비율 (없으면 열 수로 정한다)
    cols = sc.get("cols") or ([0.58, 0.42] if n == 2 else [0.24, 0.38, 0.38] if n == 3 else [1 / n] * n)
    xs = [X0]
    for c in cols:
        xs.append(xs[-1] + (X1 - X0) * c)
    rh = sc.get("row_h", 150)
    # 머리줄
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ld.rounded_rectangle([X0, y, X1, y + rh], radius=20, fill=INK)
    for k, h in enumerate(sc["header"]):
        ld.text((xs[k] + 40, y + rh / 2 - 30), h, font=F("Bold", sc.get("font", 52)), fill=PAPER)
    appear(img, lay, t, t0, dy=20)
    y += rh + 10
    for i, row in enumerate(sc["rows"]):
        hot = sc.get("highlight") == i
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        ld.rounded_rectangle([X0, y, X1, y + rh], radius=20, fill=AMBER_SOFT if hot else CARD,
                             outline=AMBER if hot else LINE, width=3)
        for k, cell in enumerate(row):
            w = "ExtraBold" if (k > 0 or hot) else "SemiBold"
            fs = fit(cell, w, sc.get("font", 58 if k else 52), (xs[k + 1] - xs[k]) - 60, 30)
            f = F(w, fs)
            col = AMBER if (k > 0 and cell in sc.get("hot", ["받아요"])) else INK
            ld.text((xs[k] + 40, y + rh / 2 - fs * 0.6), cell, font=f, fill=col)
        appear(img, lay, t, t0 + 0.4 + i * 0.45, dy=30)
        y += rh + 10
    if sc.get("note"):
        a = ease((t - t0 - 0.4 - len(sc["rows"]) * 0.45 - 0.2) / 0.4)
        if a > 0:
            d.text((X0, y + 26), sc["note"], font=F("Medium", 44), fill=SUBINK)


def s_list(img, d, sc, t):
    y = head(d, sc["title"], t)
    start = len(sc["title"]) / CPS + 0.3
    f = F("Bold", min(fit(x, "Bold", 64, X1 - X0 - 104) for x in sc["items"]))
    for item in sc["items"]:
        s, done = typed(item, t, start)
        if s:
            d.rounded_rectangle([X0, y + 8, X0 + 72, y + 80], radius=16, fill=AMBER if done else LINE)
            if done:
                d.line([(X0 + 16, y + 44), (X0 + 32, y + 60), (X0 + 57, y + 26)], fill=CARD, width=8)
            d.text((X0 + 104, y), s, font=f, fill=INK)
        y += 150
        start += len(item) / CPS + 0.25


def s_end(img, d, sc, t):
    size = min(fit(x, "ExtraBold", 100) for x in sc["lines"])
    f = F("ExtraBold", size)
    y, start = 560, 0.1
    for line in sc["lines"]:
        s, done = typed(line, t, start)
        d.text((X0, y), s, font=f, fill=INK)
        if s and not done:
            cursor(d, X0 + d.textlength(s, font=f), y, size, t)
        y += 145
        start += len(line) / CPS + 0.1
    a = ease((t - start - 0.1) / 0.4)
    if a > 0:
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        by = y + 60
        ld.rounded_rectangle([X0, by, X1, by + 140], radius=70, fill=INK)
        txt = sc["button"]
        ld.text(((X0 + X1) / 2 - ld.textlength(txt, font=F("Bold", 56)) / 2, by + 36), txt,
                font=F("Bold", 56), fill=PAPER)
        if sc.get("question"):
            ld.text((X0, by + 240), sc["question"], font=F("SemiBold", 56), fill=SUBINK)
        if sc.get("small"):  # 광고 표시 등 작은 안내
            ld.text((X0, by + 340), sc["small"], font=F("Medium", 36), fill=SUBINK)
        appear(img, lay, t, start + 0.1)


def s_photo(img, d, sc, t):
    """원본 사진 한 장을 자르지 않고 통째로 (2026-10-29 사용자: 원본 이미지로, 자르지 말고)."""
    if "_im" not in sc:
        im = Image.open(sc["src"]).convert("RGB")
        bw, bh = X1 - X0 + 60, 1180
        s = min(bw / im.width, bh / im.height)
        sc["_im"] = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS).convert("RGBA")
    im = sc["_im"]
    y = 300 + (1180 - im.height) // 2
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lay.paste(im, ((X0 + X1 + 60) // 2 - im.width // 2, y))
    ld = ImageDraw.Draw(lay)
    if sc.get("credit"):
        f = F("Medium", 28)
        c = f"© {sc['credit']}"
        ld.text(((X0 + X1 + 60) // 2 + im.width // 2 - ld.textlength(c, font=f), y + im.height + 14), c,
                font=f, fill=SUBINK)
    appear(img, lay, t, 0.0, dy=24)


DRAW = {"photo": s_photo, "quote": s_quote, "hook": s_hook, "cards": s_cards, "table": s_table, "list": s_list, "end": s_end}


def render(job, out: Path):
    set_theme(job.get("accent", "amber"), job.get("theme", "paper"))
    for sc in job["scenes"]:
        sc.setdefault("dur", auto_dur(sc))
    total = sum(sc["dur"] for sc in job["scenes"])
    p = subprocess.Popen([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
                          "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    bg = backdrop(job.get("bg"))
    elapsed, prev = 0.0, None
    for idx, sc in enumerate(job["scenes"]):
        n = round(sc["dur"] * FPS)
        for i in range(n):
            t = i / FPS
            img, d = base(job, idx, (elapsed + t) / total, bg)
            DRAW[sc["type"]](img, d, sc, t)
            last = img
            if i < 6 and prev is not None:  # 장면 첫 0.2초는 앞 장면 마지막 화면과 겹쳐 부드럽게
                img = Image.blend(prev, img, (i + 1) / 7)
            p.stdin.write(img.tobytes())
        prev = last
        elapsed += sc["dur"]
    p.stdin.close()
    p.wait()
    return total


# 견본: 2026-10-22 '퇴직금 지급기준, 계약직·알바도 받을 자격 있을까' (원고 내용만 씀)
JOB = {
    "channel": "역삼동 이선생 · 슬기로운 직장생활",
    "scenes": [
        {"type": "hook", "dur": 3.8, "lines": ["알바도", "퇴직금", "받습니다"], "em": "받습니다",
         "sub": "계약직 · 편의점 알바 모두 해당"},
        {"type": "cards", "dur": 5.0, "title": "조건은 두 가지",
         "items": [("같은 곳에서 1년 이상", "공백 없이 계속 일한 기간"),
                   ("주 15시간 이상", "4주 평균 소정근로시간")],
         "note": "근로자퇴직급여 보장법 제4조"},
        {"type": "table", "dur": 6.0, "title": "이런 경우도 받을까?", "cols": [0.64, 0.36],
         "header": ["경우", "퇴직금"],
         "rows": [["계약직", "받아요"], ["아르바이트", "받아요"], ["4대보험 미가입", "받아요"],
                  ["5인 미만 사업장", "받아요"], ["3개월씩 4번 갱신", "받아요"]],
         "note": "고용형태가 아니라 기간과 시간이 기준"},
        {"type": "table", "dur": 6.0, "title": "얼마나 받을까?", "cols": [0.58, 0.42],
         "header": ["계산", "예시"],
         "rows": [["퇴직 전 3개월 임금", "720만 원"], ["1일 평균 (÷90일)", "8만 원"],
                  ["× 30일", "240만 원"], ["근속 2년이면", "480만 원"]],
         "highlight": 3, "note": "무급휴직·병가 기간은 계산에서 뺀다"},
        {"type": "list", "dur": 6.6, "title": "놓치면 손해",
         "items": ["퇴사 후 14일 안에 지급", "안 주면 노동부에 진정", "소멸시효는 3년", "급여명세서 미리 챙기기"]},
        {"type": "end", "dur": 4.6, "lines": ["체크리스트·계산법", "전체 정리는", "블로그 글에"],
         "button": "블로그 글에서 전체 보기", "question": "퇴직금, 받아 본 적 있나요?"},
    ],
}

# 견본: 2026-10-23 '회사 밖에서도 통하는 능력 찾는 법, 명함 떼고 알았다' (에세이형, 원고 내용만 씀)
ESSAY = {
    "channel": "역삼동 이선생 · 슬기로운 직장생활",
    "scenes": [
        {"type": "quote", "dur": 5.0, "lines": ["선배, 팀장이었다는 거", "빼면 제가 뭘 했는지", "모르겠어요."],
         "who": "퇴사를 앞둔 후배 지원이"},
        {"type": "hook", "dur": 4.4, "size": 112, "lines": ["명함을 떼도", "남는 능력은", "동사에 있다"], "em": "동사",
         "sub": "직함·팀원·예산을 빼고 남는 것"},
        {"type": "table", "dur": 6.4, "title": "회사 안 vs 회사 밖", "cols": [0.24, 0.38, 0.38], "font": 46,
         "header": ["", "회사 안", "밖에서도 통함"],
         "rows": [["결정", "결재권으로", "데이터로 설득"], ["실행", "팀원에게 지시", "혼자 결과물"],
                  ["관계", "직급으로 신뢰", "처음 봐도 설득"], ["문제", "정해진 절차", "스스로 구조화"]]},
        {"type": "table", "dur": 6.0, "title": "이력서 동사 바꾸기", "cols": [0.5, 0.5],
         "header": ["이렇게 쓰면", "이렇게 바꿔요"],
         "rows": [["보고했다", "설득했다"], ["정리했다", "구조화했다"], ["담당했다", "숫자·결과로"],
                  ["총괄했다", "설계했다"]], "highlight": None,
         "note": "'담당·참여'는 자리를 말할 뿐, 행동을 말하지 않는다"},
        {"type": "quote", "dur": 5.2, "lines": ["복잡한 걸 쉬운 말로", "바꾸는 걸", "잘하는 거더라고요."],
         "who": "석 달 뒤, 다른 업계로 옮긴 지원이"},
        {"type": "end", "dur": 4.8, "lines": ["내 능력 찾는 5단계는", "블로그 글에"],
         "button": "블로그 글에서 전체 보기", "question": "회사 이름 빼고 나를 설명할 수 있나요?"},
    ],
}

if __name__ == "__main__":
    which, out = sys.argv[1], Path(sys.argv[2])  # info|essay|장면.json, 출력.mp4, [배경 사진]
    if which.endswith(".json"):
        import json
        src = json.loads(Path(which).read_text(encoding="utf-8"))
    else:
        src = JOB if which == "info" else ESSAY
    job = dict(src, bg=sys.argv[3] if len(sys.argv) > 3 else src.get("bg"))
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"[ok] {out} ({render(job, out):.1f}초)")
