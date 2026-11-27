# -*- coding: utf-8 -*-
"""[슬기로운직장생활] 네이버 원고 — 소재 발굴 → 초안 → (사용자 검사) → 이미지 (2026-11-27).

사용자: "주제 자체도 재미가 없어" / "뉴스, 검색어 등 반영해서 소재 발굴하고 초안까지 작성해두기"
       / "초안 작성 → 나한테 검사받고 → 이미지 만드는 게 좋겠어"
예전엔 구글(애드센스) 글의 검색어형 주제(연봉협상 메일, 연차 계산 …)를 네이버용으로 다시 썼는데,
네이버 이웃에게는 재미가 없어 한 편도 안 올렸다. 이제 네이버 직장생활 글은 구글 글과 주제를 따로 잡는다.

  python office.py auto            ← 자동 실행(run.py)이 부른다: 후보 5개 고르고 1번으로 초안까지
  python office.py candidates      ← 후보만 다시 뽑기
  python office.py write 3         ← 최근 후보 3번으로 초안 (또는 write "직접 정한 주제")
  python office.py finish [폴더]    ← 검사 끝난 초안으로 사진·썸네일·클립·최종 원고 (폴더 생략 시 가장 최근 초안)

저장: 드라이브 '네이버용 블로그 글/이선생/날짜 [슬기로운직장생활] 제목/'
  00_초안_검사용.txt (사용자가 읽고 고친다), _초안정보.json, 주제후보.txt
"""
import json
import os
import re
import shutil
import sys
import tempfile
import traceback
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import draft

ROOT = Path(__file__).parent
DATA = ROOT / "data"
CANDS = DATA / "office_candidates.json"
HISTORY = DATA / "office_history.json"
LOCAL_DRIVE = Path("G:/내 드라이브/네이버용 블로그 글/이선생")
SERIES = "[슬기로운직장생활]"
UA = {"User-Agent": "Mozilla/5.0"}

# 직장인이 이번 주에 같이 떠들 만한 뉴스를 찾는 검색어
NEWS_QUERIES = [
    "직장인 설문", "직장인 화제", "성과급 지급", "연말 임원 인사", "송년회 회식", "연차 소진",
    "MZ 직장인", "사내 문화", "출근 재택", "희망퇴직", "연봉 인상률", "신입 공채",
    "직장 내 괴롭힘", "주4일제", "회사 복지", "직장인 점심값", "오피스 트렌드",
]

# 달마다 직장인에게 돌아오는 일
SEASON = {
    1: ["신년 시무식", "연말정산 시작", "새해 목표·자기계발", "설 연휴 앞 선물"],
    2: ["설 연휴", "연말정산 마감", "인사평가 결과·연봉 통보", "성과급"],
    3: ["연봉협상", "신입사원 입사", "봄 이직 시즌", "주총 시즌"],
    4: ["건강보험료 정산", "벚꽃 점심", "1분기 실적"],
    5: ["가정의 달 지출", "황금연휴 연차", "종합소득세 신고(부업)"],
    6: ["상반기 평가", "여름휴가 계획", "장마철 출근"],
    7: ["여름휴가", "상반기 성과급", "복날 회식"],
    8: ["휴가 복귀 후유증", "하반기 채용"],
    9: ["추석 연휴·선물", "하반기 공채", "가을 이직"],
    10: ["국정감사·임원 보고 시즌", "내년 사업계획", "단풍 워크숍"],
    11: ["수능", "연말 인사·임원 발표", "내년 예산", "빼빼로데이", "블랙프라이데이", "건강검진 마감", "김장 휴가"],
    12: ["송년회", "연차 소진", "연말 인사 발표", "성과급 시즌", "크리스마스·연말 휴가", "올해 결산"],
}

PICK = """역삼동이선생 네이버 블로그 [슬기로운직장생활] 글감 후보 5개를 고른다. 오늘은 {today}.

## 이번에 바꾸려는 것
지금까지는 검색어형 주제(연봉협상 메일 예시, 연차 계산, 사과 메일 쓰는 법, 반대 의견 말하는 문장)를 썼는데
사용자가 재미없다고 한 편도 안 올렸다. 정보 검색용 주제는 구글 블로그가 맡는다.
네이버 이웃이 읽고 싶은 건 **지금 직장인들 사이에서 화제인 일, 몰랐던 사실(반전), 이선생이라는 사람의 생활**이다.

사용자가 실제로 올린 글의 공통점:
- 직장인 건강검진: 연말 마감이라는 시기 + 남편·후배의 실제 질문 + 과태료는 누가 내나라는 반전
- 수능 필적 확인 문구, 블랙프라이데이, 빼빼로·농심·그랜드워커힐(브랜드시선): 지금 화제 + 숫자로 뒤집는 각도

## 이선생
브랜드 마케팅 임원(여성). 남편은 제주에서 사업을 한다. 딸 써니는 스무 살 대학생(자주 쓰지 않는다).
회사 동료(30대 과장, 후배), 인사팀, 임원 회의, 출장, 송년회 같은 장면이 자연스럽다.

## 재료
[최근 7일 직장인 뉴스 제목]
{news}

[지금 네이버·구글에서 많이 입력되는 직장인 검색어 (월 검색 수)]
{queries}

[이번 달·다음 달 시즌]
{season}

[최근에 쓴(또는 후보로 냈던) 주제 — 겹치지 않게]
{past}

## 고르는 기준
- 지금 이 주에 읽어야 하는 이유가 있다 (뉴스·시즌). 언제 읽어도 같은 처세술·글쓰기 요령은 빼거나 맨 뒤로.
- 검색어 목록은 사람들이 지금 궁금해하는 쪽을 보는 데 쓴다. 검색어 그대로 정보 정리 글로 만들지 말고,
  그 검색어가 많이 나오는 이유(뉴스·시즌)와 엮어 이야기가 되는 각도를 잡는다. keyword 는 실제 검색어에서 고른다.
- 읽는 사람이 오? 하고 멈출 반전이나 몰랐던 사실이 하나 있다 (숫자, 제도, 뒷이야기).
- 동료와 점심때 수다로 꺼낼 만하다. 댓글로 각자 경험을 말하고 싶어진다.
- 5개는 서로 결이 달라야 한다: 뉴스형, 시즌형, 돈·제도형, 회사 사람 관찰형, 이선생 생활형 등 섞기.
- 후배 실수 → 조언 같은 훈계형 각도는 쓰지 않는다.
- **가장 재미있을 것부터** 순서대로. 1번은 자동으로 초안을 쓴다.

JSON 배열 하나만 출력한다 (코드펜스 없이):
[{{"title":"네이버 글 제목 안 (25~35자, 검색어 앞쪽)",
  "keyword":"네이버에서 실제로 검색할 말 (공백 없이)",
  "hook":"왜 지금인가 — 근거가 된 뉴스 제목·검색어·시즌 한 줄",
  "twist":"읽는 사람이 몰랐을 사실이나 반전 한 줄 (확인이 필요하면 확인 필요라고 적기)",
  "scene":"도입 장면 아이디어 한 줄 (누가, 어디서)",
  "why":"이 글이 재미있을 이유 한 줄"}}]"""

WRITE = """역삼동이선생 네이버 블로그 [슬기로운직장생활] 글을 쓴다. 오늘은 {today}.

[제목 안] {title}
[검색 키워드] {keyword}
[왜 지금] {hook}
[반전·몰랐던 사실] {twist}
[도입 장면 아이디어] {scene}

먼저 web_search·web_fetch 로 사실을 확인한다: 정부·공공기관(고용노동부, 국세청, 건강보험공단 등) → 회사 공식 발표 → 주요 언론 순.
숫자·날짜·제도는 확인한 것만 쓴다. 반전이 사실과 다르면 확인된 사실에 맞춰 각도를 바꾼다.

## 페르소나
{persona}

## 쓰는 법
{extra}
- 도입 장면은 지어도 되지만 확인한 사실과 어긋나면 안 된다.
- 본문은 줄글 텍스트 (HTML 아님): 문장마다 줄바꿈, 문단 사이 빈 줄 하나. 소제목 줄은 맨 앞에 "## ".
  목록은 '· ' 로 시작하는 줄. 표 쓰지 않는다.
- 소제목 4~6개 (검색어가 들어간 궁금증형). 분량 2,000~3,000자.
- 사진 자리는 한 줄에 [사진1]~[사진3] (1번은 맨 위 썸네일 자리, 나머지는 이선생 사진).
- 법·제도·숫자가 들어가면 끝에 ※ 한 줄로 기준 시점과 확인처를 적는다.
- 해시태그 10~12개 (#슬기로운직장생활 #역삼동이선생 포함, 붙여쓴 실제 검색어).

{cliche}

{style}

다 쓰면 아래 태그만 이 순서로 출력한다 (다른 말 없이):
<title>제목</title>
<alts>다른 제목 후보 2개, 한 줄에 하나</alts>
<body>본문 줄글</body>
<hashtags>#태그1 #태그2 ...</hashtags>
<checks>발행 전 다시 확인할 것, 한 줄에 하나</checks>
<sources>확인한 출처 주소, 한 줄에 하나</sources>"""


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _text(resp) -> str:
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def _safe(name: str) -> str:
    return "".join(c for c in name if c not in '\\/:*?"<>|')[:50].strip()


def put(day: str, folder: str, files: list) -> str:
    """원고 폴더에 저장. 이 PC 에서 돌리면 드라이브 동기화 폴더에 바로, 서버(Actions)면 드라이브 API 로."""
    if LOCAL_DRIVE.exists():
        dst = LOCAL_DRIVE / f"{day} {_safe(folder)}"
        dst.mkdir(parents=True, exist_ok=True)
        for f in files:
            if Path(f).resolve() != (dst / Path(f).name).resolve():
                shutil.copyfile(f, dst / Path(f).name)
        return str(dst)
    import gdrive
    return gdrive.save("이선생", day, folder, files, replace=True)


# ---------- 1. 소재 ----------
def news(days=7) -> list:
    items, seen = [], set()
    for q in NEWS_QUERIES:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": f"{q} when:{days}d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
        try:
            root = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read())
        except Exception as exc:
            log(f"  [경고] 뉴스 검색 실패 '{q}' ({type(exc).__name__})")
            continue
        for it in list(root.iter("item"))[:8]:
            t = (it.findtext("title") or "").strip()
            if t and t not in seen:
                seen.add(t)
                items.append(t)
    return items


def queries() -> list:
    """지금 많이 입력되는 직장인 검색어 (demand.py 자동완성 + 네이버 검색량)."""
    try:
        import demand
        return [f"{c['query']} (월 {c['volume']:,}회)" if "volume" in c else c["query"] for c in demand.collect()[:60]]
    except Exception as exc:
        log(f"  [경고] 검색어 수집 실패 ({type(exc).__name__}: {exc})")
        return []


def past_topics() -> list:
    out = [h["title"] for h in _load(HISTORY, [])[-40:]]
    out += [c["title"] for c in _load(CANDS, {}).get("items", [])]
    if LOCAL_DRIVE.exists():
        out += [p.name for p in sorted(LOCAL_DRIVE.iterdir())[-30:] if p.is_dir()]
        done = LOCAL_DRIVE / "발행완료"
        if done.exists():
            out += [p.name for p in done.iterdir() if p.is_dir()]
    else:  # 서버에서는 드라이브 폴더가 안 보인다 → 이미 발행한 직장생활 글을 적어 둔다
        out += ["직장인 건강검진, 안 받으면 과태료는 누가 낼까", "회의록 한 줄로 존재감 생기는 진짜 이유와 쓰는 법",
                "뒷담화 자리에서 빠져나오는 법, 적 안 만드는 멘트", "수능 필적 확인 문구"]
    return list(dict.fromkeys(out))


def candidates(client, model) -> dict:
    now = datetime.now()
    heads, qs = news(), queries()
    log(f"  뉴스 {len(heads)}건, 검색어 {len(qs)}개")
    prompt = PICK.format(today=now.strftime("%Y-%m-%d"),
                         news="\n".join(f"- {t}" for t in heads[:120]) or "(없음)",
                         queries="\n".join(f"- {q}" for q in qs) or "(없음)",
                         season=f"이번 달: {', '.join(SEASON[now.month])}\n다음 달: {', '.join(SEASON[now.month % 12 + 1])}",
                         past="\n".join(f"- {t}" for t in past_topics()) or "(없음)")
    resp = client.messages.create(model=model, max_tokens=8000, messages=[{"role": "user", "content": prompt}])
    text = _text(resp)
    items = json.loads(text[text.index("["): text.rindex("]") + 1])[:5]
    data = {"date": now.strftime("%Y-%m-%d"), "items": items}
    CANDS.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for i, c in enumerate(items, 1):
        log(f"  후보 {i}. {c['title']}")
    return data


def candidates_text(data: dict, chosen: int = 0) -> str:
    lines = [f"{SERIES} 주제 후보 — {data['date']}", ""]
    if chosen:
        lines += [f"{chosen}번으로 초안을 써 두었습니다. 다른 번호로 바꾸고 싶으면 Claude 에게 '직장생활 후보 3번으로 다시 써줘' 처럼 말하면 됩니다.", ""]
    for i, c in enumerate(data["items"], 1):
        mark = "  ← 초안 작성" if i == chosen else ""
        lines += [f"{i}. {c['title']}{mark}",
                  f"   왜 지금: {c.get('hook', '')}",
                  f"   반전: {c.get('twist', '')}",
                  f"   도입: {c.get('scene', '')}",
                  f"   재미 포인트: {c.get('why', '')}", ""]
    return "\n".join(lines)


# ---------- 2. 초안 ----------
def _persona_section() -> str:
    text = (ROOT / "persona.md").read_text(encoding="utf-8")
    m = re.search(r"## 페르소나\n(.*?)(?=\n## 글 구조)", text, re.S)
    return m.group(1).strip() if m else ""


def write_post(client, model, topic: dict) -> dict:
    import cliche
    import naver
    import style
    prompt = WRITE.format(today=datetime.now().strftime("%Y-%m-%d"), persona=_persona_section(),
                          # 구글 글이 따로 없으니 '원문 링크' 줄은 뺀다 (뉴스 링크를 붙여 오는 일이 있었다)
                          extra="\n".join(l for l in naver.LEE_EXTRA.splitlines() if "원문 링크" not in l)
                          + "\n- 본문에 외부 링크나 주소를 넣지 않는다. 출처는 <sources> 에만.", cliche=cliche.RULE, style=style.prompt_block(),
                          **{k: topic.get(k, "") for k in ("title", "keyword", "hook", "twist", "scene")})
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 10},
             {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 8}]
    messages = [{"role": "user", "content": prompt}]
    for _ in range(6):  # 서버 도구가 길어지면 pause_turn 으로 끊겨 온다 → 이어서 부른다
        with client.messages.stream(model=model, max_tokens=64000, tools=tools, messages=messages) as s:
            resp = s.get_final_message()
        if resp.stop_reason != "pause_turn":
            break
        messages = [messages[0], {"role": "assistant", "content": resp.content}]
    text = _text(resp)
    part = {k: re.search(rf"<{k}>(.*?)</{k}>", text, re.S)
            for k in ("title", "alts", "body", "hashtags", "checks", "sources")}
    if not (part["title"] and part["body"]):
        raise ValueError(f"원고 형식을 읽지 못함: {text[-300:]!r}")
    lines = lambda k: [l.strip("-· ").strip() for l in part[k].group(1).splitlines() if l.strip()] if part[k] else []
    body = part["body"].group(1).strip()
    if re.search(r"<(p|h3|br)\b", body):  # HTML 로 오면 줄글로
        body = draft.html_to_body(body)
    body = "\n".join(l for l in body.splitlines() if not re.fullmatch(r"\s*(#\S+\s*){3,}", l))  # 본문 속 태그 줄 제거
    post = {"title": part["title"].group(1).strip(), "alts": lines("alts"), "body": body,
            "hashtags": re.findall(r"#\S+", part["hashtags"].group(1)) if part["hashtags"] else [],
            "checks": lines("checks"), "sources": lines("sources")}
    return cliche.scrub_fields(client, model, post, ("title", "body"), "평어체")


def write(topic: dict, cands: dict = None, chosen: int = 0) -> str:
    """주제 하나로 초안을 쓰고 원고 폴더에 저장한다 (이미지는 만들지 않는다)."""
    from anthropic import Anthropic
    from writer import MODEL
    client = Anthropic()
    log(f"=== {SERIES} 초안: {topic['title']} ===")
    post = write_post(client, MODEL, topic)
    log(f"  제목: {post['title']} ({len(post['body'])}자)")
    day = datetime.now().strftime("%Y-%m-%d")
    work = Path(tempfile.mkdtemp())
    notes = ["발행 전 확인"] + [f"- {c}" for c in post["checks"]] + ["", "확인한 출처"] + [f"- {s}" for s in post["sources"]]
    files = draft.write(work, post["title"], post["alts"], post["body"], post["hashtags"], notes,
                        {"series": "office", "topic": topic, "checks": post["checks"], "sources": post["sources"]})
    if cands:
        (work / "주제후보.txt").write_text(candidates_text(cands, chosen), encoding="utf-8")
        files.append(work / "주제후보.txt")
    where = put(day, f"{SERIES} {post['title']}", files)
    log(f"  초안 저장: {where}")
    h = _load(HISTORY, []) + [{"date": day, "title": post["title"], "topic": topic["title"]}]
    HISTORY.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")
    return where


def auto(client, model) -> str:
    """자동 실행: 후보 5개 → 1번으로 초안."""
    data = candidates(client, model)
    return write(data["items"][0], data, 1)


def write_choice(choice: str) -> str:
    if choice.isdigit():
        data = _load(CANDS, {})
        items, n = data.get("items", []), int(choice)
        if not 1 <= n <= len(items):
            raise SystemExit(f"후보 {n}번이 없습니다 (최근 후보 {data.get('date', '없음')}, {len(items)}개).")
        return write(items[n - 1], data, n)
    return write({"title": choice, "keyword": choice.replace(" ", ""), "hook": "", "twist": "", "scene": ""})


# ---------- 3. 이미지 (검사 후) ----------
def latest_draft() -> Path:
    folders = [p for p in LOCAL_DRIVE.iterdir() if p.is_dir() and SERIES in p.name and (p / draft.DRAFT).exists()]
    if not folders:
        raise SystemExit("초안 폴더를 찾지 못했습니다.")
    return max(folders, key=lambda p: (p / draft.DRAFT).stat().st_mtime)


def make_clips(client, model, title: str, body_html: str, backdrop, folder: Path) -> list:
    """클립 2편(정보형·후킹형). run.save_clips 와 같은 이름 규칙."""
    import clipstyle
    made = []
    for kind, label in (("info", "정보형"), ("hook", "후킹형")):
        try:
            job = clipstyle.make_job(client, model, title, body_html, kind)
            out = Path(tempfile.mkdtemp()) / "out"
            video = clipstyle.build(job, out, client, model, backdrop=backdrop, remember=False)
            pairs = [(video, f"클립_{label}.mp4"), (out / "cover.jpg", f"클립_{label}_표지.jpg"),
                     (out / "caption_naver.txt", f"클립_{label}_caption_naver.txt"),
                     (out / "caption_instagram.txt", f"클립_{label}_caption_instagram.txt")]
            for src, dst in pairs:
                if src.exists():
                    shutil.copyfile(src, folder / dst)
                    made.append(folder / dst)
            log(f"  클립 {label} 완료")
        except Exception as exc:
            log(f"  [경고] 클립 {label} 실패 ({type(exc).__name__}: {exc})")
            traceback.print_exc()
    return made


def finish(folder: Path = None) -> str:
    """검사 끝난 초안(사용자가 고친 내용 그대로)으로 사진·썸네일·최종 원고·클립을 같은 폴더에 만든다."""
    from anthropic import Anthropic
    from writer import MODEL
    import naver
    import persona_photos
    from images import make_thumbnail
    client = Anthropic()
    folder = Path(folder) if folder else latest_draft()
    d = draft.read(folder)
    log(f"=== {SERIES} 이미지: {d['title']} ===")
    body_html = draft.body_to_html(d["body"])
    n = max([int(x) for x in re.findall(r"\[사진(\d+)\]", d["body"])] or [1])
    summary = re.sub(r"\s+", " ", d["body"])[:600]
    lee = persona_photos.pick(client, MODEL, d["title"], summary, n)
    work = Path(tempfile.mkdtemp())
    photos = []
    if lee:
        photos.append(make_thumbnail(d["title"], work / "thumb.png", photo=lee[0]))
        photos += lee[1:]
        persona_photos.mark([p.name for p in lee])
    files = naver.package({"title": d["title"], "body_html": body_html, "hashtags": d["hashtags"]}, photos, work / "out")
    for f in files:
        shutil.copyfile(f, folder / Path(f).name)
    log(f"  원고·사진 {len(files)}개 저장")
    if os.environ.get("CLIP_MODE", "drive") != "off":
        make_clips(client, MODEL, d["title"], body_html, lee[0] if lee else None, folder)
    return str(folder)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    args = sys.argv[1:]
    cmd = args[0] if args else ""
    if cmd == "auto":
        from anthropic import Anthropic
        from writer import MODEL
        print(auto(Anthropic(), MODEL))
    elif cmd == "candidates":
        from anthropic import Anthropic
        from writer import MODEL
        print(candidates_text(candidates(Anthropic(), MODEL)))
    elif cmd == "write" and len(args) > 1:
        print(write_choice(" ".join(args[1:])))
    elif cmd == "finish":
        print(finish(Path(" ".join(args[1:])) if len(args) > 1 else None))
    else:
        raise SystemExit('사용법: python office.py auto | candidates | write 3 | write "주제" | finish [폴더]')
