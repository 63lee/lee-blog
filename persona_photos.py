# -*- coding: utf-8 -*-
"""이선생 페르소나 사진(AI, lee-photo 스킬로 만든 것) 고르기 (2026-11-17).

사용자: "이선생 이미지 제작한 거 사용해도 되잖아" — Pixabay 대신 이선생 사진을 쓴다.
사진은 persona/ 에 있고 장면 설명은 persona/index.json. 새 사진을 만들면 같은 형식으로 추가한다.

- 구글 글과 네이버용 글은 서로 **다른** 사진을 쓴다 (같은 사진이면 네이버가 유사문서로 본다).
- 최근에 쓴 사진은 피한다 (data/persona_used.json).
"""
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
DIR = ROOT / "persona"
USED = ROOT / "data" / "persona_used.json"
CAPTION = "AI로 만든 이선생 이미지"


def _index() -> list[dict]:
    try:
        return json.loads((DIR / "index.json").read_text(encoding="utf-8"))
    except Exception:
        return []


def _used() -> list[dict]:
    try:
        return json.loads(USED.read_text(encoding="utf-8"))
    except Exception:
        return []


def mark(files: list[str]) -> None:
    log = _used() + [{"file": f, "date": date.today().isoformat()} for f in files]
    USED.parent.mkdir(parents=True, exist_ok=True)
    USED.write_text(json.dumps(log[-300:], ensure_ascii=False, indent=1), encoding="utf-8")


def pick(client, model: str, title: str, summary: str, n: int, exclude=(), prefer_face=True) -> list[Path]:
    """글에 어울리는 사진 n장을 고른다. 최근 사용한 사진은 뒤로 미룬다. 실패하면 빈 목록."""
    idx = [p for p in _index() if p["file"] not in exclude and (DIR / p["file"]).exists()]
    if not idx:
        return []
    recent = [u["file"] for u in _used()]
    # 최근에 쓴 순서대로 벌점 (가장 최근일수록 큼)
    penalty = {f: i for i, f in enumerate(recent)}
    fresh = sorted(idx, key=lambda p: penalty.get(p["file"], -1))
    pool = fresh[: max(n * 4, 10)]  # 덜 쓴 사진 중에서 고른다
    lines = "\n".join(f"{i}. [{p['kind']}] {p['scene']}" for i, p in enumerate(pool))
    want = "첫 장은 얼굴이 보이는 사진(face)으로, " if prefer_face else ""
    prompt = (f"블로그 글 제목: {title}\n요약: {summary[:400]}\n\n아래 사진 중 이 글에 가장 어울리는 {n}장을 고른다. "
              f"{want}글의 장면(사무실·회식·출근·집)과 맞는 것. 번호만 쉼표로 출력.\n{lines}")
    chosen = []
    try:
        resp = client.messages.create(model=model, max_tokens=2000, messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        for m in re.findall(r"\d+", text):
            i = int(m)
            if i < len(pool) and pool[i] not in chosen:
                chosen.append(pool[i])
    except Exception as exc:
        print(f"  [경고] 이선생 사진 고르기 실패, 덜 쓴 순서로 대신 ({type(exc).__name__})")
    for p in pool:  # 모자라면 덜 쓴 순서로 채운다
        if len(chosen) >= n:
            break
        if p not in chosen:
            chosen.append(p)
    left = len(idx) - len(set(recent[-40:]))
    if left < 8:
        print(f"  [주의] 최근에 안 쓴 이선생 사진이 {max(left, 0)}장뿐입니다. lee-photo 스킬로 새 사진을 persona/ 에 추가하세요.")
    return [DIR / p["file"] for p in chosen[:n]]
