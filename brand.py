# -*- coding: utf-8 -*-
"""[브랜드시선] 네이버용 원고 자동 작성 (2026-10-29).

매일 1편, 네이버용으로만 만든다 (Blogger 발행 없음). 기준은 brand_spec.md, 문체 견본은 data/brand_examples.md.
  1) 소재 수집: 구글뉴스(팝업·플래그십 오픈) + 시즌 달력 → Claude 가 후보 8개 → 네이버 검색량으로 거른다
     지난 브랜드시선(네이버 yanghee_11, 카테고리 49) 제목과 data/brand_history.json 으로 반복을 피한다
  2) 원고: Claude 가 웹 검색으로 사실을 확인하며 쓴다. 공식 페이지 주소도 함께 받는다
  3) 사진: 공식 페이지의 대표 이미지·본문 이미지를 받아 Claude 가 사진 자리에 맞게 고르고, 이선생 톤으로 보정
  4) 저장: 드라이브 '네이버용 블로그 글/이선생/날짜 [브랜드시선] 제목'

사용: python brand.py            (소재 자동)
      python brand.py "브랜드 소재"  (소재 지정)
      python brand.py --local 폴더   (드라이브 대신 로컬 폴더에 저장)
"""
import base64
import html
import io
import json
import os
import random
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).parent
DATA = ROOT / "data"
HISTORY = DATA / "brand_history.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
BLOG_ID, CATEGORY = "yanghee_11", 49
NEWS_QUERIES = ["팝업스토어 오픈", "플래그십스토어 오픈", "국내 첫 매장", "성수 팝업", "도산 플래그십",
                "더현대 팝업", "한정판 출시 품절", "외국인 매출 브랜드", "콜라보 출시 완판",
                # 형태가 방문기로 쏠리지 않게 (2026-10-29 사용자: 늘 이런 주제와 형태는 아니다)
                "리브랜딩 브랜드", "광고 캠페인 화제", "역대 최대 실적 브랜드", "가격 인상 브랜드",
                "단종 재출시", "브랜드명 변경", "PPL 브랜드 드라마", "캐릭터 IP 콜라보"]
FONT_B = ROOT / "fonts" / "Pretendard-Bold.otf"
FONT_XB = ROOT / "fonts" / "Pretendard-ExtraBold.otf"
NAVY, AMBER, CREAM = (16, 24, 40), (240, 168, 60), (250, 242, 228)


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def get(url, timeout=20) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


# ---------- 1. 소재 ----------
def past_titles() -> list:
    """네이버 블로그 브랜드시선 카테고리의 지난 글 제목 (최신순)."""
    seen, out = set(), []
    for page in range(1, 10):
        url = (f"https://blog.naver.com/PostTitleListAsync.naver?blogId={BLOG_ID}&viewdate=&currentPage={page}"
               f"&categoryNo={CATEGORY}&parentCategoryNo=&countPerPage=30")
        try:
            text = get(url).decode("utf-8", "replace")
        except Exception as exc:
            log(f"  [경고] 지난 글 목록 실패 ({type(exc).__name__})")
            break
        rows = re.findall(r'"title":"([^"]*)".*?"addDate":"([^"]*)"', text)
        new = [(html.unescape(urllib.parse.unquote_plus(t)), d) for t, d in rows]
        new = [r for r in new if r[0] not in seen]
        if not new:  # 마지막 쪽을 넘기면 같은 목록이 되풀이된다
            break
        for t, d in new:
            seen.add(t)
            out.append(f"{d} {t}")
    return out


def news(days=7) -> list:
    """구글뉴스 RSS 에서 최근 기사 제목."""
    items, seen = [], set()
    for q in NEWS_QUERIES:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": f"{q} when:{days}d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
        try:
            root = ET.fromstring(get(url))
        except Exception as exc:
            log(f"  [경고] 뉴스 검색 실패 '{q}' ({type(exc).__name__})")
            continue
        for it in list(root.iter("item"))[:15]:
            t = (it.findtext("title") or "").strip()
            if t and t not in seen:
                seen.add(t)
                items.append(t)
    return items


def season() -> list:
    cal = json.loads((DATA / "brand_calendar.json").read_text(encoding="utf-8"))
    now = datetime.now()
    nxt = (now.replace(day=1) + timedelta(days=32))
    return cal.get(str(now.month), []) + [f"(다음 달) {x}" for x in cal.get(str(nxt.month), [])[:3]]


def history() -> list:
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except Exception:
        return []


PICK = """역삼동이선생 네이버 블로그 [브랜드시선] 소재를 고른다. 오늘은 {today}.
[브랜드시선이란] 브랜드 방문·뉴스·시즌 이슈를 훅으로, 마케터의 눈으로 그 브랜드 전략의 의외성을 푸는 에세이.
가장 좋은 소재는 **역설**이 있는 것: 인지↑·구매↓, 한국에선 식었는데 외국인에겐 지금, 이름은 '월드'인데 미국 리그,
품절인데 매장엔 없음, 1등인데 광고를 안 함 같은 구조. 숫자로 확인할 수 있으면 더 좋다.

[최근 7일 뉴스 제목]
{news}

[이맘때 시즌·이슈]
{season}

[지난 브랜드시선 제목 — 같은 브랜드·같은 각도는 피한다. 다만 오래전 글의 브랜드를 새 각도로 다시 보는 건 괜찮다]
{past}

[최근 90일 자동 작성한 브랜드 — 반드시 피한다] {recent}

[글 형태] 아래 중 하나를 고른다. 최근에 쓴 형태({recent_forms})는 피한다.
{forms}

후보 8개를 좋은 순서로 낸다. 후보끼리도 형태를 섞는다. keyword 는 네이버에서 사람들이 실제로 검색할 말(공백 없이, 예: 마뗑킴, 뉴에라월드시리즈).
JSON 하나만 출력: {{"candidates":[{{"brand":"","keyword":"","form":"형태 이름","angle":"역설 한 줄","hook":"이선생 도입 장면 한 줄","source":"뉴스|시즌|관찰"}}]}}"""


def forms_table() -> str:
    spec = (ROOT / "brand_spec.md").read_text(encoding="utf-8")
    return spec.split("## 2-1.")[1].split("## 3.")[0]


def pick_topic(client, model, avoid=(), avoid_forms=()) -> dict:
    past, hist = past_titles(), history()
    cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    recent = [h["brand"] for h in hist if h.get("date", "") >= cutoff] + list(avoid)
    recent_forms = [h.get("form", "") for h in hist[-3:] if h.get("form")] + list(avoid_forms)
    heads = news()
    log(f"  지난 글 {len(past)}편, 뉴스 {len(heads)}건")
    prompt = PICK.format(today=datetime.now().strftime("%Y-%m-%d"), news="\n".join(f"- {h}" for h in heads[:120]),
                         season=", ".join(season()), past="\n".join(past[:150]), recent=", ".join(recent) or "없음",
                         forms=forms_table(), recent_forms=", ".join(recent_forms) or "없음")
    resp = client.messages.create(model=model, max_tokens=16000, messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in resp.content if b.type == "text")
    cands = json.loads(text[text.index("{"): text.rindex("}") + 1])["candidates"]
    cands = [c for c in cands if c.get("brand") and c["brand"] not in recent
             and c.get("form") not in recent_forms]
    import demand
    vols = demand.naver_volumes([c["keyword"] for c in cands])
    for c in cands:
        c["volume"] = vols.get(c["keyword"].replace(" ", ""))
        log(f"    후보: [{c.get('form')}] {c['brand']} ({c['keyword']} {c['volume']}) — {c['angle']}")
    # 검색량을 알 수 있으면 월 1천 미만은 뺀다 (모르면 Claude 순서 그대로)
    ok = [c for c in cands if c["volume"] is None or c["volume"] >= 1000] or cands
    return ok[0]


# ---------- 2. 원고 ----------
WRITE = """역삼동이선생 네이버 블로그 [브랜드시선] 글을 쓴다. 오늘은 {today}.

[소재] {brand} — {angle}
[글 형태] {form} — 기준의 '2-1. 글 형태' 표에서 이 형태의 구조를 따른다
[이번 글 방향] {note}
[도입 장면 아이디어] {hook}
[검색 키워드] {keyword}

먼저 web_search·web_fetch 로 사실을 모은다: 공식 홈페이지 → 공식 뉴스룸·보도자료 → 주요 언론 순.
숫자(매출·비중·가격·연도·기간), 매장 주소·운영시간, 팝업 기간은 출처를 확인한 것만 쓴다.
사진에 쓸 이미지가 있는 페이지도 찾아 둔다: 공식 홈페이지 브랜드·매장·제품 페이지, 공식 뉴스룸·보도자료,
그리고 사진 설명에 "사진=브랜드(회사)"로 표기된 **회사 제공 보도사진**이 실린 기사. 5곳 이상.
기자가 직접 찍은 사진·개인 블로그·인스타는 넣지 않는다.

## 기준 (반드시 지킨다)
{spec}

## 문체 견본 — 이 두 글의 리듬·위트·구조를 따른다 (내용은 베끼지 않는다)
{examples}

## 쓰는 법
- 평어체. 도입부 이선생 장면은 자유롭게 만들어도 되지만, 브랜드에 대한 사실은 확인한 것만.
- 만든 장면도 확인한 사실과 어긋나면 안 된다: 개점·출시일 전에 그 매장에 갔다거나, 팝업 기간이 아닌 날 다녀왔다고 쓰지 않는다.
  ("지난주 토요일 2호점 줄" ← 2호점이 어제 열었다면 틀린 장면)
- 본문은 줄글. 소제목 줄은 맨 앞에 "## ". 사진 자리는 한 줄에 [사진1] 처럼 (6~8자리, 훅 직후 첫 사진).
- 비교 표는 "구분 | 그때 | 지금" 처럼 | 로 나눈 줄들 (첫 줄이 머리줄).
- 방문 정보(오픈·방문형일 때만)는 "방문 정보" 소제목 아래 "· 위치: …" 줄들.
- 끝은 "Q. …" 한 줄, 그 다음 "※함께 읽으면 좋은 글" 아래 지난 글 제목 하나: {related}

{cliche}

다 쓰면 JSON 하나만 출력한다 (코드펜스 없이):
{{"titles":["[브랜드시선] …","…","…"],
 "body":"본문 전체 (줄바꿈은 \\n)",
 "photos":[{{"slot":1,"want":"어떤 사진이 필요한지 (예: 성수 매장 외관)","caption":"▲ 캡션 (출처 표기는 빼고)"}}],
 "hashtags":["#…"],
 "official_pages":[{{"url":"https://…","name":"ⓒ 뒤에 쓸 출처 이름 (공식 홈페이지면 '마뗑킴 공식 홈페이지', 회사 제공 보도사진이면 '롯데칠성음료')"}}],
 "sources":["확인한 출처 주소"],
 "checks":["발행 전 다시 확인할 것"]}}"""


def _text_and_json(resp) -> str:
    return "".join(b.text for b in resp.content if b.type == "text")


def write_post(client, model, topic: dict, related: str) -> dict:
    spec = (ROOT / "brand_spec.md").read_text(encoding="utf-8").split("## 7.")[0]
    import cliche
    prompt = WRITE.format(today=datetime.now().strftime("%Y-%m-%d"), spec=spec, related=related or "(없으면 생략)",
                          examples=(DATA / "brand_examples.md").read_text(encoding="utf-8"),
                          cliche=cliche.RULE, **{k: topic.get(k, "") for k in ("brand", "angle", "hook", "keyword", "form", "note")})
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 12},
             {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 10}]
    messages = [{"role": "user", "content": prompt}]
    for _ in range(6):  # 서버 도구가 길어지면 pause_turn 으로 끊겨 온다 → 이어서 부른다
        with client.messages.stream(model=model, max_tokens=64000, tools=tools, messages=messages) as s:
            resp = s.get_final_message()
        if resp.stop_reason != "pause_turn":
            break
        messages = [messages[0], {"role": "assistant", "content": resp.content}]
    text = _text_and_json(resp)
    post = json.loads(text[text.index("{"): text.rindex("}") + 1])
    cliche.scrub_fields(client, model, post, ("body",), "평어체")
    return post


# ---------- 3. 사진 ----------
def page_images(url: str) -> list:
    """공식 페이지의 대표 이미지(og:image)와 본문 이미지 주소."""
    try:
        doc = get(url).decode("utf-8", "replace")
    except Exception:
        return []
    found = re.findall(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)', doc)
    found += re.findall(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)', doc)
    found += re.findall(r'<img[^>]+(?:data-src|src)=["\']([^"\']+\.(?:jpe?g|png|webp)[^"\']*)', doc, re.I)
    out = []
    for u in found:
        u = urllib.parse.urljoin(url, html.unescape(u))
        if u.startswith("http") and not re.search(r"logo|icon|sprite|banner_s|btn|blank|pixel", u, re.I):
            out.append(u)
    return list(dict.fromkeys(out))


def collect_photos(pages: list, work: Path, limit=24) -> list:
    """[{path, name, url}] — 600px 이상인 사진만."""
    work.mkdir(parents=True, exist_ok=True)
    got, keys = [], []
    for p in pages:
        for u in page_images(p["url"])[:20]:
            try:
                im = Image.open(io.BytesIO(get(u)))
                if im.mode in ("RGBA", "LA", "P"):  # 투명 배경 제품 컷은 검게 변하지 않게 밝은 바탕에 얹는다
                    im = im.convert("RGBA")
                    bg = Image.new("RGB", im.size, (246, 244, 240))
                    bg.paste(im, mask=im.getchannel("A"))
                    im = bg
                im = im.convert("RGB")
            except Exception:
                continue
            if min(im.size) < 600:
                continue
            # 같은 사진이 주소만 다르게(?p=twitter / ?p=facebook) 여러 번 걸리는 일이 있어 그림으로 비교한다
            key = im.convert("L").resize((16, 16)).tobytes()
            if any(sum(abs(a - b) for a, b in zip(key, k)) < 16 * 16 * 6 for k in keys):
                continue
            keys.append(key)
            path = work / f"cand{len(got):02d}.jpg"
            im.save(path, quality=92)
            got.append({"path": path, "name": p["name"], "url": u})
            if len(got) >= limit:
                return got
    return got


ASSIGN = """블로그 글 사진 자리에 넣을 사진을 고른다. 위 후보 {n}장(0번부터).
[글] {title}
[사진 자리]
{slots}
자리마다 맞는 후보 번호를 하나씩 고른다. 같은 사진은 두 번 쓰지 않는다. 맞는 사진이 없으면 -1.
글자·가격표가 화면 대부분인 배너, 로고만 있는 이미지, 흐린 사진은 고르지 않는다.
JSON 하나만: {{"pick": {{"1": 번호, "2": 번호, ...}}}}"""


def assign_photos(client, model, post, cands) -> dict:
    content = []
    for i, c in enumerate(cands):
        im = Image.open(c["path"])
        im.thumbnail((420, 420))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
        content += [{"type": "text", "text": f"후보 {i}"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                 "data": base64.b64encode(buf.getvalue()).decode()}}]
    slots = "\n".join(f"{p['slot']}: {p['want']}" for p in post["photos"])
    content.append({"type": "text", "text": ASSIGN.format(n=len(cands), title=post["titles"][0], slots=slots)})
    resp = client.messages.create(model=model, max_tokens=16000, messages=[{"role": "user", "content": content}])
    text = _text_and_json(resp)
    pick = json.loads(text[text.index("{"): text.rindex("}") + 1])["pick"]
    return {int(k): int(v) for k, v in pick.items() if 0 <= int(v) < len(cands)}


def polish(src: Path, dst: Path):
    """이선생 톤 (lee-photo-consistency): 1080 정사각, 같은 보정, 오른쪽 아래 서명. 흐린 여백 채우기 금지."""
    im = ImageOps.fit(Image.open(src).convert("RGB"), (1080, 1080), Image.LANCZOS, centering=(0.5, 0.45))
    # 화이트밸런스: 채널 평균을 절반만큼 회색 쪽으로
    r, g, b = [c for c in im.split()]
    means = [sum(c.histogram()[i] * i for i in range(256)) / (1080 * 1080) for c in (r, g, b)]
    gray = sum(means) / 3
    im = Image.merge("RGB", [c.point(lambda v, k=(1 + (gray / max(m, 1) - 1) * 0.5): min(255, int(v * k)))
                             for c, m in zip((r, g, b), means)])
    lum = sum(i * n for i, n in enumerate(im.convert("L").histogram())) / (1080 * 1080)
    im = ImageEnhance.Brightness(im).enhance(min(max(128 / max(lum, 1), 0.88), 1.18))
    im = ImageEnhance.Color(im).enhance(0.92)
    im = ImageEnhance.Contrast(im).enhance(1.04)
    # 크림톤 하이라이트
    mask = im.convert("L").point(lambda v: max(0, v - 150) * 0.5)
    im = Image.composite(Image.blend(im, Image.new("RGB", im.size, CREAM), 0.35), im, mask)
    # 약한 비네팅
    v = Image.new("L", (1080, 1080), 0)
    ImageDraw.Draw(v).ellipse((-180, -180, 1260, 1260), fill=255)
    v = v.filter(ImageFilter.GaussianBlur(160))
    im = Image.composite(im, ImageEnhance.Brightness(im).enhance(0.8), v)
    # 그레인
    grain = Image.effect_noise((1080, 1080), 40).point(lambda v: v - 128 + 128)
    im = Image.blend(im, Image.merge("RGB", (grain,) * 3), 0.035)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(str(FONT_B), 26)
    d.text((1080 - 40 - d.textlength("역삼동이선생", font=f), 1080 - 58), "역삼동이선생", font=f, fill=(245, 242, 236))
    im.save(dst, quality=90)


def thumbnail(title: str, photo: Path, dst: Path):
    """1080x1350: 위쪽 남색 판에 라벨·제목(마지막 줄 amber), 아래 사진. 뉴에라 글 썸네일과 같은 구성."""
    W, H = 1080, 1350
    # 위 560px 은 남색 판(라벨·제목), 사진은 그 아래에만 깐다. 인물·포스터는 얼굴이 위쪽이라
    # 사진 위쪽 기준으로 자른다 (2026-10-29: 전면에 깔았더니 남색 판이 배우 얼굴을 가렸다)
    top = 560
    im = Image.new("RGB", (W, H), NAVY)
    ph = ImageOps.fit(Image.open(photo).convert("RGB"), (W, H - top + 160), Image.LANCZOS, centering=(0.5, 0.2))
    fade = Image.new("L", ph.size, 255)
    fd = ImageDraw.Draw(fade)
    for y in range(160):  # 사진 윗부분 160px 이 남색 판으로 스며든다
        fd.line((0, y, W, y), fill=int(255 * y / 160))
    im.paste(ph, (0, top - 160), fade)
    d = ImageDraw.Draw(im)
    fl = ImageFont.truetype(str(FONT_B), 34)
    a, b = "역삼동이선생의 ", "브랜드시선"
    tw = d.textlength(a + b, font=fl)
    d.rounded_rectangle((60, 110, 60 + tw + 72, 110 + 72), radius=36, fill=(248, 246, 242))
    d.text((96, 126), a, font=fl, fill=NAVY)
    d.text((96 + d.textlength(a, font=fl), 126), b, font=fl, fill=AMBER)
    d.line((60, 250, W - 60, 250), fill=(200, 200, 205), width=2)
    words = re.sub(r"^\[[^\]]+\]\s*", "", title).replace(",", "").split()
    size = 84
    while True:  # 세 줄 안에 들어가는 가장 큰 글자
        f = ImageFont.truetype(str(FONT_XB), size)
        lines, cur = [], ""
        for w in words:
            if d.textlength(f"{cur} {w}".strip(), font=f) <= W - 130:
                cur = f"{cur} {w}".strip()
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        if len(lines) <= 3 or size <= 56:
            break
        size -= 6
    y = 300
    for k, ln in enumerate(lines[:3]):
        d.text((60, y), ln, font=f, fill=AMBER if k == len(lines[:3]) - 1 else (255, 255, 255))
        y += int(size * 1.32)
    # 아래 '역삼동이선생' 서명은 넣지 않는다 (2026-10-29 사용자: 고정 로고가 부담스럽다)
    im.save(dst, quality=90)


# ---------- 4. 클립 ----------
CLIP_MEMO = ("\n\n[클립 메모] 결말·반전 같은 스포일러는 클립에서 밝히지 않고 '블로그에서' 로 궁금하게 남긴다. "
             "클립에 나오지 않는 브랜드의 사진은 쓰지 않는다.")


def make_clips(client, model, title: str, out: Path, work: Path) -> list:
    """원고 폴더(out)의 원고·원본 사진으로 정보형·후킹형 클립 (2026-10-29 사용자가 정한 세트).
    원본 사진을 자르지 않고, 로고 없이. 사진이 2장 미만이면 정보형만. 하나가 실패해도 다른 하나·원고는 그대로."""
    import shutil
    import clipstyle
    text = (out / "00_네이버용_원고.txt").read_text(encoding="utf-8")
    body = text.split("---", 1)[1].split("발행 전 확인")[0] + CLIP_MEMO
    name = re.sub(r"^\[[^\]]+\]\s*", "", title)
    photos = [p for p in (out / "원본").iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    made = []
    for style, label in (("info", "정보형"), ("hook", "후킹형")):
        if style == "hook" and len(photos) < 2:
            log("  [경고] 후킹형 클립 건너뜀: 공식 사진이 2장 미만")
            continue
        try:
            job = clipstyle.make_job(client, model, name, body, style, series="브랜드시선")
            co = work / f"clip_{style}"
            video = clipstyle.build(job, co, client, model, photo_dir=(out / "원본") if photos else None,
                                    remember=False)
            pairs = [(video, f"클립_{label}.mp4"), (co / "cover.jpg", f"클립_{label}_표지.jpg"),
                     (co / "caption_naver.txt", f"클립_{label}_caption_naver.txt"),
                     (co / "caption_instagram.txt", f"클립_{label}_caption_instagram.txt")]
            for src, dst in pairs:
                if src.exists():
                    shutil.copy(src, out / dst)
                    made.append(out / dst)
            log(f"  클립 {label} 완료")
        except Exception as exc:
            log(f"  [경고] 클립 {label} 실패 ({type(exc).__name__}: {exc})")
    return made


# ---------- 5. 정리·저장 ----------
def renumber(body: str, keep: dict) -> tuple:
    """사진 자리 번호를 1부터 다시 매긴다. (본문, {새 번호: 옛 번호})
    사진을 못 찾은 자리도 남긴다 — 사용자가 직접 찍은 사진·캡처를 넣는다."""
    order, new = {}, 0

    def sub(m):
        nonlocal new
        new += 1
        order[new] = int(m.group(1))
        return f"[사진{new}]"
    body = re.sub(r"\[사진(\d+)\]", sub, body)
    return re.sub(r"\n{3,}", "\n\n", body), order


def to_html(title, body, captions, tags, names) -> str:
    out, rows = [], []

    def flush():
        if rows:
            head, *rest = rows
            t = "<table style='border-collapse:collapse;width:100%;font-size:15px'>"
            t += "<tr>" + "".join(f"<th style='border:1px solid #ccc;padding:6px;background:#f3f1ec'>{html.escape(c)}</th>"
                                  for c in head) + "</tr>"
            t += "".join("<tr>" + "".join(f"<td style='border:1px solid #ccc;padding:6px'>{html.escape(c)}</td>"
                                          for c in r) + "</tr>" for r in rest)
            out.append(t + "</table>")
            rows.clear()
    for line in body.split("\n"):
        s = line.strip()
        if "|" in s and s.count("|") >= 1 and not s.startswith("http"):
            rows.append([c.strip() for c in s.split("|")])
            continue
        flush()
        if not s:
            continue
        m = re.fullmatch(r"\[사진(\d+)\]", s)
        if m:
            n = int(m.group(1))
            label = names.get(n, "")
            label = label if label.startswith("(") else f"← {label}"
            out.append(f"<p style='background:#fff3cd;padding:6px 10px'>📷 [사진{n}] {html.escape(label)}</p>"
                       f"<p style='color:#777;font-size:14px'>{html.escape(captions.get(n, ''))}</p>")
        elif s.startswith("## "):
            out.append(f"<h3>{html.escape(s[3:])}</h3>")
        else:
            out.append(f"<p>{html.escape(s)}</p>")
    flush()
    return (f"<!doctype html><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<div style='max-width:720px;margin:30px auto;font:16px/1.8 sans-serif'>"
            f"<p style='color:#888;font-size:13px'>제목과 본문을 복사해 네이버 블로그에 붙여넣으세요. "
            f"노란 표시 자리에 같은 번호의 사진을, 아래 회색 글은 사진 설명 칸에 넣으면 됩니다.</p>"
            f"<h2>{html.escape(title)}</h2>{''.join(out)}<p>{html.escape(tags)}</p></div>")


def to_text(post, body, captions, order_names) -> str:
    lines = []
    for line in body.split("\n"):
        m = re.fullmatch(r"\s*\[사진(\d+)\]\s*", line)
        if m:
            n = int(m.group(1))
            lines.append(f"[사진{n}] {order_names.get(n, '')}")
            lines.append(captions.get(n, ""))
        else:
            lines.append(line[3:] if line.startswith("## ") else line)
    out = [post["titles"][0], "", "(다른 제목 후보)", *[f"- {t}" for t in post["titles"][1:]], "", "---", "",
           "\n".join(lines), "", " ".join(post.get("hashtags", [])), "", "---", "발행 전 확인",
           *[f"- {c}" for c in post.get("checks", [])], "", "확인한 출처", *[f"- {s}" for s in post.get("sources", [])]]
    return "\n".join(out) + "\n"


def run(topic_text: str = None, local: Path = None, redo_photos: bool = False, avoid=(), avoid_forms=(),
        topic_opts: dict = None) -> Path:
    from anthropic import Anthropic
    from writer import MODEL
    client = Anthropic()
    log("=== 브랜드시선 시작 ===")
    if redo_photos:  # 마지막 원고로 사진·정리만 다시 (원고는 그대로)
        post = json.loads((DATA / "brand_last.json").read_text(encoding="utf-8"))
        topic = post["_topic"]
    else:
        if topic_text:  # 사용자가 소재를 정할 때: --form= --angle= --note= 로 형태·각도·방향도 줄 수 있다
            topic = {"brand": topic_text, "hook": "", "keyword": topic_text.replace(" ", ""), **(topic_opts or {})}
        else:
            topic = pick_topic(client, MODEL, avoid, avoid_forms)
        log(f"  소재: [{topic.get('form', '')}] {topic['brand']} — {topic.get('angle', '')}")
        past = past_titles()
        related = random.choice(past[:40]).split(" ", 3)[-1] if past else ""
        post = write_post(client, MODEL, topic, related)
        post["_topic"] = topic
        (DATA / "brand_last.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
    # 본문 끝에 해시태그 줄을 넣어 오는 일이 있다 → 본문에서 빼고 hashtags 로만 쓴다 (두 번 찍히지 않게)
    post["body"] = "\n".join(l for l in post["body"].split("\n")
                              if not re.fullmatch(r"\s*(#\S+\s*){3,}", l)).rstrip()
    title = post["titles"][0]
    log(f"  원고: {title} ({len(post['body'])}자)")

    import tempfile
    work = Path(tempfile.mkdtemp())
    cands = collect_photos(post.get("official_pages", []), work / "cand")
    log(f"  사진 후보 {len(cands)}장")
    pick = assign_photos(client, MODEL, post, cands) if len(cands) >= 2 else {}
    body, order = renumber(post["body"], pick)
    caps_by_old = {p["slot"]: p.get("caption", "") for p in post["photos"]}
    out = work / "out"
    (out / "원본").mkdir(parents=True)
    files, captions, names, credits = [], {}, {}, []
    wants = {p["slot"]: p.get("want", "") for p in post["photos"]}
    for new, old in order.items():
        if old not in pick:
            captions[new] = caps_by_old.get(old, "").strip()
            names[new] = f"(공식 사진 없음 — 직접 넣기: {wants.get(old, '')})"
            continue
        c = cands[pick[old]]
        cap = caps_by_old.get(old, "").strip()
        captions[new] = f"{cap} ⓒ {c['name']}" if cap else f"ⓒ {c['name']}"
        name = f"{new + 1:02d}_사진{new}.jpg"
        polish(c["path"], out / name)
        Image.open(c["path"]).save(out / "원본" / name, quality=95)
        names[new] = name
        files.append(out / name)
        credits.append(f"{name}\t{c['name']}\t{c['url']}")
    first = next((pick[o] for o in order.values() if o in pick), None)
    if first is not None:
        thumbnail(title, cands[first]["path"], out / "01_썸네일.jpg")
        files.insert(0, out / "01_썸네일.jpg")
    tags = " ".join(post.get("hashtags", []))
    (out / "00_네이버용_원고.html").write_text(to_html(title, body, captions, tags, names), encoding="utf-8")
    (out / "00_네이버용_원고.txt").write_text(to_text(post, body, captions, names), encoding="utf-8")
    (out / "사진출처.txt").write_text("\n".join(credits) + "\n", encoding="utf-8")
    texts = [out / "00_네이버용_원고.html", out / "00_네이버용_원고.txt", out / "사진출처.txt"]
    clips = [] if os.environ.get("BRAND_CLIPS", "on") == "off" else make_clips(client, MODEL, title, out, work)

    day = datetime.now().strftime("%Y-%m-%d")
    folder = f"[브랜드시선] {re.sub(r'^\[[^\]]+\]\s*', '', title)}"
    if local:
        import shutil
        dst = local / f"{day} {''.join(c for c in folder if c not in chr(92) + '/:*?\"<>|')[:60].strip()}"
        shutil.copytree(out, dst, dirs_exist_ok=True)
        where = str(dst)
    else:
        import gdrive
        originals = [out / "원본" / n for n in names.values() if n.endswith(".jpg")]
        for p in originals:  # 드라이브엔 하위 폴더 없이 '원본_' 이름으로
            p.rename(out / f"원본_{p.name}")
        where = gdrive.save("이선생", day, folder, texts + files + clips
                            + [out / f"원본_{n}" for n in names.values() if n.endswith(".jpg")])
    if not redo_photos:
        h = history() + [{"date": day, "brand": topic["brand"], "form": topic.get("form", ""), "title": title}]
        HISTORY.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"  저장: {where} (사진 {len(files) - (first is not None)}장 / 자리 {len(order)}개 / 클립 파일 {len(clips)}개)")
    return out


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    args = sys.argv[1:]
    local = None
    if "--local" in args:
        i = args.index("--local")
        local = Path(args[i + 1])
        del args[i:i + 2]
    redo = "--redo-photos" in args
    # 예: --avoid=치폴레,캪틴큐  --avoid-form=오픈·방문형
    avoid = next((a.split("=", 1)[1].split(",") for a in args if a.startswith("--avoid=")), [])
    avoid_forms = next((a.split("=", 1)[1].split(",") for a in args if a.startswith("--avoid-form=")), [])
    opts = {k: next((a.split("=", 1)[1] for a in args if a.startswith(f"--{k}=")), "")
            for k in ("form", "angle", "note")}
    args = [a for a in args if a != "--redo-photos" and not a.startswith(("--avoid", "--form=", "--angle=", "--note="))]
    run(args[0] if args else None, local, redo, avoid, avoid_forms, opts)
