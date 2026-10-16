# -*- coding: utf-8 -*-
"""오늘 쓸 주제를 고른다.

두 갈래로 뽑는다.
  1) 트렌드 트랙 — Google Trends 일간 인기 검색어 중 니치에 맞는 것
  2) 에버그린 트랙 — 트렌드에 건질 게 없는 날 쓰는 검색 수명 긴 주제

한국 일간 트렌드 상위는 대부분 스포츠·연예라서, 실제로는 에버그린이
주력이고 트렌드는 가끔 얹히는 보너스로 보는 게 맞다.
"""
import json
import random
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from niche import EVERGREEN_TOPICS, niche_score

TRENDS_URL = "https://trends.google.co.kr/trending/rss?geo=KR"
HISTORY_PATH = Path(__file__).parent / "data" / "history.json"
NS = {"ht": "https://trends.google.com/trending/rss"}


def load_history() -> dict:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return {"used": []}


def save_history(history: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def fetch_trends() -> list[dict]:
    """Google Trends 일간 인기 검색어를 가져온다. 실패해도 예외를 던지지 않는다."""
    req = urllib.request.Request(TRENDS_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        raw = urllib.request.urlopen(req, timeout=20).read()
    except Exception as exc:  # 네트워크 문제로 하루치 실행이 죽지 않게 한다
        print(f"  [경고] 트렌드 수집 실패: {exc}")
        return []

    root = ET.fromstring(raw)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        traffic = (item.findtext("ht:approx_traffic", namespaces=NS) or "0").strip()
        headlines = [
            (n.findtext("ht:news_item_title", namespaces=NS) or "").strip()
            for n in item.findall("ht:news_item", NS)
        ]
        items.append(
            {
                "keyword": title,
                "traffic": traffic,
                "headlines": [h for h in headlines if h][:3],
            }
        )
    return items


def pick_trend_topics(used: set[str]) -> list[dict]:
    """니치 필터를 통과한 트렌드 키워드만 골라 점수순으로 돌려준다."""
    picked = []
    for item in fetch_trends():
        # 점수는 키워드로, 차단 판정은 헤드라인까지 보고 한다.
        score, cat = niche_score(item["keyword"], " ".join(item["headlines"]))
        if score <= 0 or item["keyword"] in used:
            continue
        picked.append({**item, "score": score, "category": cat, "track": "trend"})

    picked.sort(key=lambda x: x["score"], reverse=True)
    return picked


def pick_evergreen_topics(used: set[str], count: int) -> list[dict]:
    """아직 안 쓴 에버그린 주제를 슬기로운 직장생활 우선으로 뽑는다."""
    pool = [(c, t) for c, t in EVERGREEN_TOPICS if t not in used]
    if not pool:
        print("  [경고] 에버그린 주제 풀이 모두 소진됐습니다. niche.py에 추가하세요.")
        return []

    # 바닥나기 전에 미리 알린다. 다 떨어진 날 아침에야 알면 이미 늦다.
    if len(pool) <= 10:
        print(f"  [주의] 남은 주제가 {len(pool)}개뿐입니다 (약 {len(pool) // 2}일치). "
              "niche.py의 EVERGREEN_TOPICS를 보충하세요.")

    # 슬기로운 직장생활이 주축: office 3 : career 2 : brand 1 비중.
    # 하루 2편씩만 뽑으므로, 지금까지 쓴 비율과 목표 비율의 차이가 가장 큰 쪽부터 채운다.
    # (단순히 순서대로 섞으면 매일 office 만 뽑히고 나머지는 영영 안 나온다)
    share = {"office": 3, "career": 2, "brand": 1}
    cat_of = {t: c for c, t in EVERGREEN_TOPICS}
    done = {c: 0 for c in share}
    for entry in load_history()["used"]:
        c = cat_of.get(entry["keyword"])
        if c in done:
            done[c] += 1
    buckets = {c: [p for p in pool if p[0] == c] for c in share}
    for items in buckets.values():
        random.shuffle(items)

    ordered = []
    while any(buckets.values()) and len(ordered) < count:
        total = sum(done.values()) + 1
        cat = max((c for c in share if buckets[c]),
                  key=lambda c: share[c] / sum(share.values()) - done[c] / total)
        ordered.append(buckets[cat].pop())
        done[cat] += 1

    return [
        {
            "keyword": topic,
            "traffic": "-",
            "headlines": [],
            "score": 0,
            "category": cat,
            "track": "evergreen",
        }
        for cat, topic in ordered[:count]
    ]


def pick_today(count: int) -> list[dict]:
    """오늘 쓸 주제 count개를 고른다. 트렌드를 먼저 채우고 나머지는 에버그린으로.

    여기서는 기록하지 않는다. 초안 작성이 실패한 주제까지 '사용함'으로
    남으면 그 주제를 영영 못 쓰게 되기 때문에, 기록은 성공한 뒤에
    mark_used()로 따로 남긴다.
    """
    used = {entry["keyword"] for entry in load_history()["used"]}
    topics = pick_trend_topics(used)[:count]
    if len(topics) < count:
        topics += pick_evergreen_topics(used, count - len(topics))
    return topics


def mark_used(topic: dict) -> None:
    """초안 작성에 성공한 주제를 기록해 다음 실행에서 중복되지 않게 한다."""
    history = load_history()
    # --topic으로 같은 주제를 다시 뽑으면 기록이 중복된다. 한 번만 남긴다.
    if any(e["keyword"] == topic["keyword"] for e in history["used"]):
        return
    history["used"].append(
        {"keyword": topic["keyword"], "date": date.today().isoformat(), "track": topic["track"]}
    )
    save_history(history)


if __name__ == "__main__":
    for t in pick_today(3):
        print(f"[{t['track']:9}] [{t['category']}] {t['keyword']}  (traffic={t['traffic']})")
