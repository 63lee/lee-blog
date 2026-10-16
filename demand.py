# -*- coding: utf-8 -*-
"""그날그날 직장인이 많이 검색하는 주제를 고른다 (2026-10-16).

1) 직장인 관련 씨앗 키워드로 네이버·구글 자동완성을 수집한다.
   자동완성은 지금 많이 입력되는 검색어 순서로 나오므로 '현재 검색 수요'의 근사치다.
2) Google Trends 일간 인기 검색어 중 직장인 관련 것을 더한다.
3) 드라마·연예·스포츠 등 엉뚱한 검색어를 거른다.
4) Claude 가 후보 중에서 30~40대 직장인이 지금 가장 궁금해할 주제를 고르고,
   검색어를 살린 글 주제 문장으로 바꾼다.

후보가 모자라거나 실패하면 빈 목록을 돌려주고, 호출 쪽이 기존 주제 풀로 넘어간다.
"""
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime

from niche import BLOCK_TERMS

UA = {"User-Agent": "Mozilla/5.0"}

# 30~40대 직장인이 검색창에 치는 말머리. 자동완성이 뒤를 채워 준다.
SEEDS = [
    "직장인", "회사", "팀장", "상사", "직장 동료", "신입사원", "중간관리자",
    "연봉", "연봉협상", "성과급", "이직", "퇴사", "퇴직금", "실업급여", "권고사직",
    "연말정산", "직장인 재테크", "직장인 부업", "직장인 대출", "직장인 적금",
    "육아휴직", "출산휴가", "워킹맘", "연차", "야근", "재택근무", "주4일제",
    "회식", "보고서", "회의", "업무 이메일", "직장 스트레스", "번아웃",
    "승진", "인사평가", "구조조정", "희망퇴직", "정년", "직장인 건강검진",
    "직장인 자기계발", "직장인 대학원", "직장인 자격증", "ai 업무",
]

# 직장인 주제가 아닌 것으로 자주 섞이는 말
EXTRA_BLOCK = [
    "드라마", "웹툰", "다시보기", "출연진", "몇부작", "결말", "ott", "영화", "예고",
    "골프챔피언십", "짤", "영어로", "뜻", "게임", "노래", "가사", "강회장",
    "시즌", "직장인 들", "직장인들", "회차", "방영", "재방송", "넷플릭스", "티빙", "쿠팡플레이",
]


def _get_json(url: str):
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8"))


def naver_suggest(q: str) -> list[str]:
    url = "https://ac.search.naver.com/nx/ac?" + urllib.parse.urlencode({
        "q": q, "con": "1", "frm": "nv", "ans": "2", "r_format": "json", "r_enc": "UTF-8",
        "r_unicode": "0", "t_koreng": "1", "run": "2", "rev": "4", "q_enc": "UTF-8", "st": "100"})
    try:
        return [i[0] for i in _get_json(url).get("items", [[]])[0]]
    except Exception:
        return []


def google_suggest(q: str) -> list[str]:
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        {"client": "firefox", "hl": "ko", "q": q})
    try:
        return _get_json(url)[1]
    except Exception:
        return []


NAVER_STATUS = "미확인"


def naver_volumes(queries: list[str]) -> dict:
    """네이버 검색광고 API 키워드 도구로 월간 검색량(PC+모바일)을 받는다.

    키(NAVER_AD_CUSTOMER_ID / NAVER_AD_API_KEY / NAVER_AD_SECRET)가 없거나 실패하면 빈 dict.
    API 는 공백 없는 키워드만 받고, 한 번에 5개까지라 나눠서 부른다.
    """
    import base64
    import hashlib
    import hmac
    import time

    # 붙여넣을 때 따옴표·공백·줄바꿈이 섞여 들어오는 일이 잦아 정리한다
    def _clean(name):
        return os.environ.get(name, "").strip().strip('"').strip("'").strip()
    cid, key, secret = _clean("NAVER_AD_CUSTOMER_ID"), _clean("NAVER_AD_API_KEY"), _clean("NAVER_AD_SECRET")
    global NAVER_STATUS
    missing = [n for n, v in (("NAVER_AD_CUSTOMER_ID", cid), ("NAVER_AD_API_KEY", key),
                              ("NAVER_AD_SECRET", secret)) if not v]
    if missing:
        NAVER_STATUS = f"Secrets 없음: {', '.join(missing)}"
        return {}

    def _n(v):  # "< 10" 같은 값도 온다
        return int(v) if str(v).isdigit() else 5

    vols: dict[str, int] = {}
    hints = list(dict.fromkeys(q.replace(" ", "") for q in queries))
    for i in range(0, len(hints), 5):
        batch = hints[i:i + 5]
        ts = str(int(time.time() * 1000))
        sig = base64.b64encode(hmac.new(secret.encode(), f"{ts}.GET./keywordstool".encode(),
                                        hashlib.sha256).digest()).decode()
        url = "https://api.searchad.naver.com/keywordstool?" + urllib.parse.urlencode(
            {"hintKeywords": ",".join(batch), "showDetail": "1"})
        req = urllib.request.Request(url, headers={
            "X-Timestamp": ts, "X-API-KEY": key, "X-Customer": cid, "X-Signature": sig})
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
        except Exception as exc:
            # 오류 메시지에 키가 들어가지 않게 종류와 HTTP 코드만 남긴다
            code = getattr(exc, "code", "")
            detail = ""
            if hasattr(exc, "read"):
                try:
                    detail = json.loads(exc.read().decode("utf-8")).get("title", "")[:80]
                except Exception:
                    pass
            NAVER_STATUS = f"API 오류 {type(exc).__name__} {code} {detail}".strip()
            print(f"  [경고] 네이버 검색량 조회 실패 ({NAVER_STATUS}) — 자동완성 순위로 진행")
            return vols
        for row in data.get("keywordList", []):
            if row["relKeyword"] in batch:
                vols[row["relKeyword"]] = _n(row.get("monthlyPcQcCnt")) + _n(row.get("monthlyMobileQcCnt"))
        time.sleep(0.2)
    NAVER_STATUS = "정상"
    return vols


def _blocked(q: str) -> bool:
    low = q.lower()
    return any(b in q for b in BLOCK_TERMS) or any(b in low for b in EXTRA_BLOCK)


def collect() -> list[dict]:
    """후보 검색어를 모은다. 여러 곳·앞순위에 나올수록 점수가 높다."""
    score: dict[str, float] = {}
    for seed in SEEDS:
        for source in (naver_suggest, google_suggest):
            for rank, q in enumerate(source(seed + " ")[:10]):
                q = re.sub(r"\s+", " ", q).strip()
                if len(q) < 4 or q == seed or _blocked(q):
                    continue
                score[q] = score.get(q, 0) + (10 - rank) / 10
    try:
        from keywords import fetch_trends
        from niche import niche_score
        for item in fetch_trends():
            s, cat = niche_score(item["keyword"], " ".join(item["headlines"]))
            if s > 0 and cat in ("office", "career"):
                score[item["keyword"]] = score.get(item["keyword"], 0) + 3
    except Exception:
        pass
    ranked = sorted(score.items(), key=lambda kv: -kv[1])
    cands = [{"query": q, "score": round(s, 2)} for q, s in ranked]

    # 네이버 검색광고 키가 있으면 상위 후보의 실제 월간 검색량으로 다시 정렬한다
    top = cands[:120]
    vols = naver_volumes([c["query"] for c in top])
    if vols:
        for c in top:
            c["volume"] = vols.get(c["query"].replace(" ", ""), 0)
        top.sort(key=lambda c: -c["volume"])
        print(f"  네이버 월간 검색량 반영: {len(vols)}개 (최다: {top[0]['query']} {top[0]['volume']:,}회)")
        return top
    return cands


PICK_PROMPT = """너는 '역삼동이선생의 슬기로운 직장생활' 블로그 편집장이다.
독자는 30~40대 직장인이다. 오늘은 {today}이다.

아래는 오늘 네이버·구글에서 실제로 많이 입력되는 직장인 관련 검색어 후보다 (월 검색 수 또는 점수가 높을수록 검색이 많다).
{candidates}

이미 쓴 주제 (비슷한 건 피한다):
{used}

할 일: 오늘 쓸 글 주제 {count}개를 고른다.
- 검색량(점수)이 높고, 30~40대 직장인이 지금 실제로 궁금해할 것을 우선한다.
- 시기성(연말정산 시즌, 성과급 시즌, 인사철 등)이 맞으면 가산점.
- 이 블로그의 구글판 목적은 **구글 애드센스 수익**이다. 광고 단가(CPC)가 높은 돈·법·세금·급여·보험·대출·
  퇴직금·실업급여·연말정산 관련 주제에 가산점을 준다. 단, 검색량이 너무 적은 주제는 피한다.
- 단순 쇼핑·상품 추천(가방, 백팩, 선물 리스트)은 피하고, 일·관계·돈·마음·커리어에 대한 글이 되는 것을 고른다.
- 서로 다른 갈래(예: 하나는 일/관계, 하나는 돈/커리어)로 고른다.
- search_keyword 는 후보 검색어를 그대로 쓴다 (제목 앞쪽에 넣을 핵심 키워드).

다음 JSON 배열만 출력한다:
[{{"search_keyword": "후보 검색어 그대로", "topic": "글 주제 한 문장", "category": "office 또는 career", "why": "고른 이유 한 줄"}}]"""


def pick(used: set[str], count: int) -> list[dict]:
    try:
        cands = collect()
    except Exception as exc:
        print(f"  [경고] 검색어 수집 실패: {exc}")
        return []
    if len(cands) < 10:
        print(f"  [경고] 검색어 후보가 {len(cands)}개뿐이라 기존 주제 풀을 씁니다.")
        return []
    print(f"  검색어 후보 {len(cands)}개 수집 (상위: {', '.join(c['query'] for c in cands[:5])})")

    from anthropic import Anthropic
    from writer import MODEL
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = PICK_PROMPT.format(
        today=datetime.now().strftime("%Y년 %m월 %d일"),
        candidates="\n".join(
            f"- {c['query']} (월 {c['volume']:,}회 검색)" if "volume" in c else f"- {c['query']} ({c['score']})"
            for c in cands[:80]),
        used="\n".join(f"- {u}" for u in sorted(used)[-80:]) or "(없음)",
        count=count,
    )
    try:
        resp = client.messages.create(model=MODEL, max_tokens=1500,
                                      messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        picked = json.loads(text[text.index("["): text.rindex("]") + 1])
    except Exception as exc:
        print(f"  [경고] 주제 선정 실패: {exc}")
        return []

    topics = []
    for p in picked[:count]:
        if p["topic"] in used:
            continue
        topics.append({
            "keyword": p["topic"],
            "search_keyword": p.get("search_keyword", ""),
            "traffic": "-",
            "headlines": [],
            "score": 0,
            "category": p.get("category", "office"),
            "track": "demand",
            "why": p.get("why", ""),
        })
    for t in topics:
        print(f"  검색 수요 주제: [{t['search_keyword']}] {t['keyword']} — {t['why']}")
    return topics
