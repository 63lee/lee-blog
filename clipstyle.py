# -*- coding: utf-8 -*-
"""블로그 글 → 글에 맞는 스타일의 무음 클립 (2026-10-29).

사용자: "클립 스타일이 별로야", "글에 따라서 스타일이 자유자재로 변형되어야 해", "음성 빼줘, 어색해".
그래서 예전 한 가지 틀(명조 제목 + 스톡 영상 + TTS)을 버리고, Claude 가 글을 읽고 셋 중 하나를 고른다.
  info  : 정보형 (info_clip.py) — 기준·조건·숫자·비교·단계가 있는 글. 표·카드·체크리스트
  hook  : 후킹 리스트형 (photo_clip.py) — 'N가지 말·방법·팁' 글. 사진 + 태그 + 두 줄 헤드라인
  place : 현장형 (photo_clip.py) — 장소·매장·골프장·팝업 방문기. 사진 + 담백한 가운데 자막 + 정보 카드
색·바탕·길이·장면 수도 글마다 다르게 정한다. 참고 클립 4편은 드라이브 '네이버용 블로그 글' 의
이선생 2026-10-22 정보형_견본, 2026-10-27 스카이밸리CC, 패션/패션 클립 2편.

사용: python clipstyle.py <글.html> [출력 폴더] [사진 폴더]   (사진 폴더를 주면 그 사진을 쓴다: 직접 찍은 현장 사진)
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import cliche
from clip import FF

ROOT = Path(__file__).parent
RECENT = ROOT / "data" / "clip_styles.json"

PROMPT = """아래 블로그 글로 네이버 클립(인스타 릴스 겸용) 세로 영상을 만든다. **내레이션 없이 화면 글자만으로** 전달하는 영상이다.
글쓴이는 회사 생활을 오래 한 브랜드 마케터 출신 직장 선배 '역삼동이선생'(여성). 시리즈: {series}. 딸 써니는 스무 살. '25년' 같은 경력 연수는 말하지 않는다.

[글 제목] {title}
[글 본문]
{body}

## 1. 스타일 고르기 — 글의 재료에 맞춰 고른다
- "info"  정보형: 조건·기준·숫자·금액·기간·비교(A vs B)·단계·체크리스트가 글에 있을 때. 노동법·돈·제도·이직 준비 등.
          밝은 종이(paper) 또는 어두운(night) 바탕에 큰 글자, 번호 카드, 표, 체크리스트가 차례로 나온다. 30~40초.
- "hook"  후킹 리스트형: 바로 써먹는 말·습관·방법을 3~5개로 나눌 수 있을 때. "이렇게 말한다", "N가지".
          사진을 꽉 채우고 위에 태그(01 / 말투) + 두 줄 헤드라인, 아래 짧은 설명. 장면이 빠르게 넘어간다. 18~25초.
- "place" 현장형: 특정 장소·매장·골프장·팝업·전시를 다녀온 글일 때만.
          사진 위 가운데 담백한 두 줄 자막, 끝에 이름·주소 같은 정보 카드. 30~40초.
{recent}
## 2. 공통 규칙
- 클립은 글의 요약이 아니다. 60초 안에 에세이 논리를 압축하면 근거 없는 주장의 나열이 된다.
  **바로 써먹을 수 있는 구체적인 것**(문장·숫자·기준·체크 항목)을 화면에 준다. 더 자세한 건 블로그로 보낸다.
- 첫 화면에서 멈추게 한다: 공감 가는 상황이나 의외의 답을 짧게.
- 화면 글자는 짧게. 평어체(~다) 또는 명사로 끝낸다. 마지막 질문만 "~있나요?" 같은 물음.
- 글에 없는 사실·숫자·일화를 지어내지 않는다. 인물 설명도 글에 있는 만큼만 (써니 나이·학년, 후배 직급을 덧붙이지 않는다).
- 대사·바꿔 말할 문장은 “ ” 로 감싼다.
- accent: 강조색. 글 분위기에 맞게 고른다.
  info → "amber" "coral" "teal" "blue" "green" 중 하나 / hook·place → "lime" "amber" "coral" "sky" "mint" "pink" 중 하나.

## 3. 스타일별 scenes
### info (theme: "paper" 또는 "night") — 장면 5~7개, 종류를 섞어 리듬을 만든다
- {{"type":"hook","lines":["알바도","퇴직금","받습니다"],"em":"받습니다","sub":"계약직 · 편의점 알바 모두 해당"}}
  lines 2~3줄, 한 줄 2~6자. em 은 lines 중 한 줄 안의 낱말(형광펜). 첫 장면은 hook 또는 quote.
- {{"type":"quote","lines":["선배, 팀장이었다는 거","빼면 제가 뭘 했는지","모르겠어요."],"who":"퇴사를 앞둔 후배"}}
  글 속 실제 대사가 있을 때만. 한 줄 12자 안팎.
- {{"type":"cards","title":"조건은 두 가지","items":[["같은 곳에서 1년 이상","공백 없이 계속 일한 기간"],["주 15시간 이상","4주 평균 소정근로시간"]],"note":"근로자퇴직급여 보장법 제4조"}}
  items 2~3개, 큰 글 11자 이내, 작은 글 18자 이내. note 는 없어도 된다.
- {{"type":"table","title":"이렇게 바꿔 말한다","header":["이렇게 말하면","이렇게 바꿔요"],"rows":[["틀렸는데요","같이 볼까요?"]],"hot":["같이 볼까요?"],"highlight":null,"note":""}}
  2열이면 칸마다 10자 이내, 3열이면 6자 이내. rows 3~5개. hot: 강조색으로 칠할 칸 글자. highlight: 강조할 줄 번호 또는 null.
- {{"type":"list","title":"놓치면 손해","items":["퇴사 후 14일 안에 지급","소멸시효는 3년"]}}  items 3~4개, 14자 이내.
- 마지막 end 장면은 따로 쓰지 않는다 (아래 end 로 만든다).

### hook — 장면 5~6개
- 공통: label = 영문 대문자 꼬리표 (예: "WORK TALK / 4 WAYS", "MONEY CHECK / 3 STEPS")
- 장면: {{"tag":"01 / 말투","head":["회의 중 실수 발견","“같이 볼까요?”로 시작"],"chip":"상대 체면부터 살린다","query":"meeting notebook pen"}}
  첫 장면 tag 는 주제 꼬리표(예: "WORK TALK"), head 는 질문형 훅. 가운데 장면 tag 는 "01 / 낱말"처럼 번호.
  마지막 장면 tag 는 "SAVE THIS" 같은 저장 유도. head 두 줄은 각각 13자 이내(둘째 줄이 강조색). chip 20자 이내.
- query: Pixabay 세로 사진 영어 검색어 2~4단어. **사람 얼굴이 나오지 않는 사물·공간·손**
  (책상, 노트, 커피, 사무실 창가, 키보드 위 손 등). 침대·슬립·CG·일러스트 금지. 장면마다 다르게.

### place — 장면 7~10개
- 공통: place = {{"kicker":"여주 골프장","name":"스카이밸리CC","tag":"여주 · 스카이밸리CC","info":[["주소","경기 여주시 …"],["코스","36홀 …"]]}}
  info 는 글에 있는 사실만 1~3개.
- 장면: {{"sub":"통유리 로비 너머로\\n소나무 숲이 보인다","em":"소나무 숲","query":"glass lobby pine forest"}}
  sub 는 두 줄, 한 줄 15자 이내, 의미 단위로 나눈다. em 은 sub 속 낱말. 첫 장면 sub 는 장소를 소개.

## 4. end (모든 스타일)
{{"lines":["체크리스트·계산법","전체 정리는","블로그 글에"],"button":"블로그 글에서 전체 보기","question":"퇴직금, 받아 본 적 있나요?"}}
lines 2~3줄(한 줄 11자 이내). question 은 댓글을 부르는 질문 하나.

## 5. 캡션
- caption: 네이버 클립 캡션. 3~4줄 요약 + "연결된 블로그 글에 정리해 뒀다" + 질문 1개 + 해시태그 8~9개
  (#역삼동이선생 #{series_tag} 포함).
- caption_instagram: 핵심 2줄 + "프로필 링크의 블로그 글" 안내 + 저장 유도 1줄 + 질문 1개 + 해시태그 6~7개.
- cover: 표지에 크게 쓸 제목 2~3줄 (한 줄 8자 안팎, 마지막 줄이 강조색).

{cliche_rule}

다음 JSON 하나만 출력한다 (코드펜스 없이):
{{"style":"info|hook|place","why":"고른 이유 한 줄","accent":"","theme":"paper","label":"","place":null,
  "scenes":[...],"end":{{"lines":[],"button":"블로그 글에서 전체 보기","question":""}},
  "cover":["",""],"caption":"","caption_instagram":""}}"""


def _plain(body_html: str) -> str:
    t = re.sub(r"<(script|style).*?</\1>", " ", body_html, flags=re.S)
    t = re.sub(r"</t[dh]>", " | ", t)
    t = re.sub(r"<(br|/p|/h[1-6]|/li|/tr)[^>]*>", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"<[^>]+>", "", t)).strip()


def _recent() -> list:
    try:
        return json.loads(RECENT.read_text(encoding="utf-8"))[-4:]
    except Exception:
        return []


def _remember(style: str):
    RECENT.parent.mkdir(exist_ok=True)
    RECENT.write_text(json.dumps((_recent() + [style])[-8:]), encoding="utf-8")


def _ok(job) -> bool:
    if job.get("style") not in ("info", "hook", "place") or len(job.get("scenes", [])) < 3:
        return False
    if job["style"] == "place" and not (job.get("place") or {}).get("name"):
        return False
    return bool(job.get("end", {}).get("lines"))


def make_job(client, model: str, title: str, body_html: str, style: str = None,
             series: str = "슬기로운 직장생활") -> dict:
    """style 을 주면 그 스타일로 만든다 (사용자가 스타일을 정해 다시 만들 때).
    series: 블로그 시리즈 이름 — 화면 위 채널 이름과 해시태그에 쓴다 (2026-10-29 브랜드시선 추가)."""
    rec = _recent()
    recent = (f"\n최근 클립 스타일: {', '.join(rec)}. 글 재료가 둘 다 맞으면 최근과 다른 쪽을 고른다.\n"
              if rec else "")
    if style:
        recent = f"\n**이번에는 반드시 \"{style}\" 스타일로 만든다** (사용자 지정).\n"
    prompt = PROMPT.format(title=title, body=_plain(body_html)[:7000], recent=recent, cliche_rule=cliche.RULE,
                           series=series, series_tag=series.replace(" ", ""))
    last = None
    for _ in range(2):
        # thinking 모델이라 max_tokens 가 작으면 빈 답이 온다
        resp = client.messages.create(model=model, max_tokens=16000,
                                      messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        try:
            job = json.loads(text[text.index("{"): text.rindex("}") + 1])
            if _ok(job) and (not style or job["style"] == style):
                break
            last = "형식 불일치"
        except ValueError as exc:
            last = exc
    else:
        raise ValueError(f"클립 대본을 읽지 못함: {last}")
    cliche.scrub_fields(client, model, job, ("caption", "caption_instagram"), "평어체")
    job["title"] = title
    job.setdefault("channel", f"역삼동 이선생 · {series}" if job["style"] == "info" else "역삼동 이선생")
    print(f"  클립 스타일: {job['style']} / {job.get('accent')} — {job.get('why', '')}")
    return job


# ---------- 사진 ----------
def _pixabay(query: str, orientation: str) -> list:
    key = os.environ.get("PIXABAY_API_KEY", "").strip().strip('"').strip("'")
    if not key:
        from clip import env
        key = env("PIXABAY_API_KEY")
    url = "https://pixabay.com/api/?" + urllib.parse.urlencode({
        "key": key, "q": query, "image_type": "photo", "orientation": orientation,
        "safesearch": "true", "per_page": 30, "min_height": 1400, "order": "popular"})
    # User-Agent 가 없으면 Pixabay(Cloudflare)가 403(1010)으로 막는다
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (lee-blog)"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read()).get("hits", [])


PICK = """세로 클립 한 장면의 배경 사진을 고른다. 위 사진 {n}장(0번부터).
[클립 주제] {title}
[이 장면에 얹을 글자] {text}

반드시 지킬 것 — 하나라도 어기면 그 사진은 탈락:
- 사진 안에 글자·숫자·연도·로고·손글씨가 읽히면 탈락 (화면 글자와 겹쳐 지저분해진다)
- 사람 얼굴이 보이면 탈락 (손·뒷모습·실루엣은 괜찮다)
- 침대·잠옷·성당·관광지·CG·일러스트처럼 직장 장면과 상관없으면 탈락
남은 사진 중 장면 글자와 분위기가 맞고, 위쪽이 단순해 글자를 얹기 좋은 것을 고른다.
모두 탈락이면 -1. JSON 하나만: {{"pick": 번호}}"""

FALLBACK = ["desk notebook coffee", "office window light", "laptop keyboard hands",
            "paper documents desk", "pen notebook writing", "empty office chair"]


def _choose(client, model, title, text, hits) -> int:
    """후보 사진을 받아서(base64) Claude 에게 보여 준다. 마땅한 게 없으면 -1."""
    import base64
    content = []
    for h in hits:
        try:
            req = urllib.request.Request(h["webformatURL"], headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=20).read()
            kind = "image/png" if raw[1:4] == b"PNG" else "image/jpeg"
            content.append({"type": "image", "source": {"type": "base64", "media_type": kind,
                                                        "data": base64.b64encode(raw).decode()}})
        except Exception:
            content.append({"type": "text", "text": "(불러오지 못함 — 탈락)"})
    content.append({"type": "text", "text": PICK.format(n=len(hits), title=title, text=text)})
    try:
        resp = client.messages.create(model=model, max_tokens=16000, messages=[{"role": "user", "content": content}])
        out = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        k = int(json.loads(out[out.index("{"): out.rindex("}") + 1])["pick"])
        return k if -1 <= k < len(hits) else -1
    except Exception as exc:
        print(f"  [경고] 사진 고르기 실패 ({type(exc).__name__})")
        return 0


def scene_photos(client, model, job, out_dir: Path) -> list:
    """장면마다 Pixabay 세로 사진 1장. 후보를 Claude 가 보고 고르고, 마땅한 게 없으면 다른 검색어로 다시 찾는다.
    (2026-10-29: 연도가 찍힌 다이어리, 성당, 얼굴 나온 회의 사진이 걸려서 탈락 기준을 엄격히 했다)"""
    import images
    out_dir.mkdir(parents=True, exist_ok=True)
    used = set(images._used_ids())
    paths = []
    for i, sc in enumerate(job["scenes"]):
        text = " / ".join(sc.get("head", [])) or sc.get("sub", "")
        hit = None
        for q in [sc.get("query") or "office desk"] + FALLBACK[i % len(FALLBACK):] + FALLBACK[:i % len(FALLBACK)]:
            try:
                hits = _pixabay(q, "vertical")
                if len(hits) < 4:
                    hits += _pixabay(q, "all")
            except Exception as exc:
                print(f"  [경고] 사진 검색 실패 ({type(exc).__name__})")
                continue
            hits = [h for h in hits if f"pixabay-{h['id']}" not in used][:8]
            if not hits:
                continue
            k = _choose(client, model, job["title"], text, hits) if client else 0
            if k >= 0:
                hit = hits[k]
                break
            print(f"  장면 {i + 1}: '{q}' 후보 탈락, 다른 검색어로")
        if hit is None:  # 끝까지 없으면 앞 장면 사진을 다시 쓴다 (장면과 사진 순서가 어긋나지 않게)
            if paths:
                paths.append(paths[-1])
            continue
        path = out_dir / f"scene{i:02d}.jpg"
        req = urllib.request.Request(hit["largeImageURL"], headers={"User-Agent": "Mozilla/5.0"})
        path.write_bytes(urllib.request.urlopen(req, timeout=30).read())
        images._mark_used(f"pixabay-{hit['id']}")
        used.add(f"pixabay-{hit['id']}")
        paths.append(path)
    if not paths:
        raise RuntimeError("장면 사진을 하나도 받지 못함")
    return paths


def match_photos(client, model, job, photos: list) -> list:
    """직접 찍은 사진 폴더를 쓸 때: Claude 가 사진을 보고 장면 자막에 맞는 사진을 장면마다 고른다.
    (파일 이름 순서대로 쓰면 '그늘집 골뱅이무침' 자막에 조각상 사진이 걸린다)"""
    import base64
    import io
    from PIL import Image
    content = []
    credit = {}  # 원고 폴더의 사진출처.txt 가 있으면 출처도 알려 준다 (다른 브랜드 사진이 엉뚱한 장면에 가지 않게)
    src = photos[0].parent.parent / "사진출처.txt" if photos else None
    if src and src.exists():
        for line in src.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                credit[parts[0]] = parts[1]
    for i, p in enumerate(photos[:20]):
        im = Image.open(p).convert("RGB")
        im.thumbnail((400, 400))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
        content += [{"type": "text", "text": f"사진 {i}" + (f" (출처: {credit[p.name]})" if p.name in credit else "")},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                 "data": base64.b64encode(buf.getvalue()).decode()}}]
    subs = "\n".join(f"{k}: {sc.get('sub') or ' / '.join(sc.get('head', []))}".replace("\n", " ")
                     for k, sc in enumerate(job["scenes"]))
    content.append({"type": "text", "text": f"""위 사진 {len(content) // 2}장으로 세로 클립을 만든다. 장면 자막은 아래와 같다.
{subs}
장면마다 자막 내용과 가장 맞는 사진 번호를 하나씩 고른다. 같은 사진은 되도록 두 번 쓰지 않는다.
자막과 어긋나는 사진은 쓰지 않는다: 자막이 말하는 브랜드·행사·장소와 다른 출처의 사진을 그 장면에 놓지 않는다
(예: 디즈니 팝업 이야기에 편의점 상품 사진). 자막에 한 번도 나오지 않는 브랜드의 사진은 어느 장면에도 쓰지 않는다. 맞는 사진이 없으면 그 작품·브랜드의 대표 사진(포스터 등)을 쓴다.
첫 장면은 주제가 한눈에 보이는 사진. 다음 JSON 하나만 출력한다: {{"photos": [번호, ...]}}"""})
    try:
        resp = client.messages.create(model=model, max_tokens=16000, messages=[{"role": "user", "content": content}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        idx = json.loads(text[text.index("{"): text.rindex("}") + 1])["photos"]
        picked = [photos[int(i)] for i in idx if 0 <= int(i) < len(photos)]
        if len(picked) >= len(job["scenes"]):
            print(f"  사진 배치: {[p.name for p in picked]}")
            return picked[:len(job["scenes"])]
    except Exception as exc:
        print(f"  [경고] 사진 배치 실패, 이름 순서대로 사용 ({type(exc).__name__})")
    return photos


# ---------- 조립 ----------
def build(job: dict, out: Path, client=None, model=None, photo_dir: Path = None, backdrop: Path = None,
          remember: bool = True) -> Path:
    """영상·표지·캡션을 out 폴더에 만든다. 돌려주는 값은 영상 경로."""
    out.mkdir(parents=True, exist_ok=True)
    video = out / "clip.mp4"
    (out / "clip.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    style = job["style"]
    credit_of = {}
    if photo_dir:  # 원고 폴더의 사진출처.txt (파일 이름 → ⓒ 이름)
        src = Path(photo_dir).parent / "사진출처.txt"
        if src.exists():
            for line in src.read_text(encoding="utf-8").splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    credit_of[parts[0]] = parts[1]
    if style == "info":
        import info_clip
        scenes = [dict(sc) for sc in job["scenes"]]
        if photo_dir:  # 원본 사진은 배경으로 흐리게 깔지 않고, 장면 사이에 통째로 끼운다
            photos = sorted(p for p in Path(photo_dir).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
            for k, ph in enumerate(photos[:3]):
                scenes.insert(1 + k * 3, {"type": "photo", "src": str(ph), "credit": credit_of.get(ph.name, "")})
            backdrop = None
        scenes.append({"type": "end", **job["end"]})
        render_job = {"channel": job["channel"], "accent": job.get("accent"), "theme": job.get("theme", "paper"),
                      "bg": str(backdrop) if backdrop and backdrop.exists() else None, "scenes": scenes}
        total = info_clip.render(render_job, video)
        cover_t = scenes[0]["dur"] - 0.2
    else:
        import photo_clip
        if photo_dir:
            photos = sorted(p for p in Path(photo_dir).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
            if client:
                photos = match_photos(client, model, job, photos)
        else:
            photos = scene_photos(client, model, job, out / "photos")
        total = photo_clip.render(job, photos, video, fit=bool(photo_dir),
                                  credits=[credit_of.get(Path(p).name, "") for p in photos])
        cover_t = photo_clip.scene_dur(job, job["scenes"][0]) - 0.2
    # 표지: 첫 장면 글자가 다 나온 순간
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{max(cover_t, 0.5):.2f}",
                    "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out / "cover.jpg")], check=True)
    (out / "caption_naver.txt").write_text(job.get("caption", ""), encoding="utf-8")
    if job.get("caption_instagram"):
        (out / "caption_instagram.txt").write_text(job["caption_instagram"], encoding="utf-8")
    if remember:  # 브랜드시선처럼 스타일을 정해서 만든 클립은 직장생활 클립의 '최근 스타일'에 넣지 않는다
        _remember(style)
    print(f"[ok] {video} ({style}, {total:.1f}초)")
    return video


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from anthropic import Anthropic
    from writer import MODEL
    force = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--style=")), None)  # 예: --style=info
    series = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--series=")), "슬기로운 직장생활")
    sys.argv = [a for a in sys.argv if not a.startswith(("--style=", "--series="))]
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix("")
    photo_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    client = Anthropic()
    if src.suffix == ".json":  # 이미 만든 대본으로 다시 렌더
        job = json.loads(src.read_text(encoding="utf-8"))
    else:
        html = src.read_text(encoding="utf-8")
        m = re.search(r"<title>(.*?)</title>|<h1[^>]*>(.*?)</h1>|^#[ \t]+([^\n]+)", html, re.S | re.M)
        title = re.sub(r"<[^>]+>", "", (m.group(1) or m.group(2) or m.group(3))).strip() if m else src.stem
        job = make_job(client, MODEL, title, html, force, series)
    imgs = src.parent / (src.stem + "-images")
    build(job, out, client, MODEL, photo_dir, backdrop=imgs / "photo1.jpg")
