# -*- coding: utf-8 -*-
"""애드센스 '가치가 별로 없는 콘텐츠' 반려 대응 (2026-11-17).

1) 이미 쓴 글과 주제가 겹치는지 본다 — 같은 주제를 제목만 바꿔 두 번 쓴 글이
   (칭찬 잘하는 팀장, 첫 월급 분배, 연봉 실수령액) 반려 원인 중 하나였다.
2) 새 글 끝에 실제로 발행된 관련 글 링크를 붙인다 — 글끼리 이어지는 구조를 만든다.
   (이메일 게시는 라벨을 못 달아서 카테고리 구조가 사실상 없다)

블로그 피드를 못 읽어도 예외를 던지지 않는다. 그때는 발행 기록만으로 판단한다.
"""
import json
import re
import urllib.request

FEED = "https://63lee.blogspot.com/feeds/posts/summary?alt=json&max-results=500"

# 제목에 흔히 붙는 말. 이것까지 비교하면 서로 다른 주제도 비슷해 보인다.
_STOP = ["이유", "방법", "정리", "진짜", "하는 법", "는 법", "차이", "기준", "직장인", "회사",
         "이렇게", "한다", "다르다", "까지", "부터", "에서", "총정리", "완벽정리",
         "무엇이", "무엇을", "다른가", "하는가", "되는가", "어떻게", "언제", "실제로", "생기는", "할 일"]

_cache: list[dict] | None = None


def _norm(text: str) -> str:
    text = re.sub(r"[^0-9A-Za-z가-힣 ]", " ", text)
    for w in _STOP:
        text = text.replace(w, " ")
    return re.sub(r"\s+", "", text)


def _grams(text: str) -> set[str]:
    t = _norm(text)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def similarity(a: str, b: str) -> float:
    """두 제목(주제)의 글자 두 개씩 묶음 겹침 정도 (짧은 쪽 기준, 0~1)."""
    ga, gb = _grams(a), _grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / min(len(ga), len(gb))


def published() -> list[dict]:
    """블로그에 실제로 올라간 글 [{title, url}] (최신순). 실패하면 빈 목록."""
    global _cache
    if _cache is not None:
        return _cache
    try:
        req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
        posts = []
        for e in data["feed"].get("entry", []):
            url = next((l["href"] for l in e.get("link", []) if l.get("rel") == "alternate"), "")
            if url:
                posts.append({"title": e["title"]["$t"], "url": url})
        _cache = posts
    except Exception as exc:
        print(f"  [경고] 블로그 피드 읽기 실패: {exc}")
        _cache = []
    return _cache


DUP_LIMIT = 0.5


def closest(topic: str, others: list[str]) -> tuple[float, str]:
    best = (0.0, "")
    for o in others:
        s = similarity(topic, o)
        if s > best[0]:
            best = (s, o)
    return best


def is_duplicate(topic: str, others: list[str]) -> bool:
    score, other = closest(topic, others)
    if score >= DUP_LIMIT:
        print(f"  중복 주제 제외: '{topic}' ≈ '{other}' ({score:.2f})")
        return True
    return False


def related_html(title: str, n: int = 3) -> str:
    """새 글과 가까운 기존 글 n개를 '함께 읽으면 좋은 글' 블록으로."""
    cands = []
    for p in published():
        if p["title"] == title:
            continue
        s = similarity(title, p["title"])
        if 0.12 <= s < 0.9:  # 너무 멀면 상관없는 글, 너무 가까우면 같은 글
            cands.append((s, p))
    cands.sort(key=lambda x: -x[0])
    picked = [p for _, p in cands[:n]]
    if len(picked) < n:  # 모자라면 최근 글로 채운다
        for p in published():
            if p not in picked and p["title"] != title:
                picked.append(p)
            if len(picked) >= n:
                break
    if not picked:
        return ""
    items = "".join(f'<li><a href="{p["url"]}">{p["title"]}</a></li>' for p in picked)
    return f'<h3>함께 읽으면 좋은 글</h3><ul>{items}</ul>'
