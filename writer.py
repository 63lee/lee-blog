# -*- coding: utf-8 -*-
"""Claude API로 초안을 쓴다."""
import json
import os
import re
from pathlib import Path

from anthropic import Anthropic

MODEL = "claude-sonnet-5"
# 본문 + 확장 사고까지 담아야 한다. 부족하면 JSON이 중간에 잘려 파싱이 깨진다.
MAX_TOKENS = 16000
PERSONA = (Path(__file__).parent / "persona.md").read_text(encoding="utf-8")

SYSTEM = f"""당신은 네이버·구글 블로그 '역삼동이선생'의 글을 대신 쓴다.
아래 지침을 문자 그대로 지킨다.

{PERSONA}

## 출력 형식
JSON 하나를 쓰고, 그 아래 `===BODY===` 한 줄, 그 아래 본문 HTML을 쓴다.
본문은 JSON 안에 넣지 않는다. 코드펜스도, 설명도 붙이지 않는다.

{{
  "titles": ["제목 후보1", "제목 후보2", "제목 후보3"],
  "title_notes": ["후보1의 SEO/AEO 관점 한 줄 설명", "...", "..."],
  "meta_description": "검색 결과에 노출될 요약. 80~120자.",
  "labels": ["태그1", "태그2", "..."],
  "quote_cards": ["카드로 만들 핵심 문장1", "핵심 문장2"],
  "image_query": "도입부 사진을 찾을 영문 검색어",
  "asset_type": "template | examples | table | checklist | none",
  "asset_reason": "그 자산을 넣은(혹은 넣지 않은) 이유 한 줄",
  "fact_check_notes": ["초안에 쓴 수치·사실 중 발행 전 반드시 검증해야 할 항목"]
}}
===BODY===
<p>본문 HTML을 여기에 그대로 쓴다. 이스케이프하지 않는다.</p>

## 본문 규칙
- 태그는 <p>, <h2>, <h3>, <ul>, <ol>, <li>, <strong>, <blockquote>,
  그리고 표에 쓰는 <table>, <thead>, <tbody>, <tr>, <th>, <td>만 쓴다.
- <h1>은 쓰지 않는다 (제목이 h1을 차지한다).
- 마지막 문단은 반드시 <p><strong>Q.</strong> 로 시작하는 댓글 유도 질문이다.
- 본문 3,000자 이상. h2 소제목 5~7개.

## 실용 자산 규칙 (중요)

검색으로 들어온 사람이 **당장 복사해서 쓸 수 있는 것**을 원하는 주제라면,
본문 안에 실용 자산을 직접 넣는다. 파일 다운로드가 아니라 본문에 넣는다.

**넣어야 하는 주제 (도구형 검색 의도)**
"양식", "예시", "계산", "방법", "절차", "기준"을 찾아 검색하는 주제.
경력기술서·이력서, 면접 답변, 수당·급여 계산, 신고 절차, 협상 화법 등이 해당한다.

**넣지 말아야 하는 주제 (에세이형)**
감정·조직문화·브랜드 분석처럼 공감하러 오는 주제. 여기에 양식을 넣으면
글의 결이 깨진다. 이 경우 asset_type을 "none"으로 하고 억지로 만들지 않는다.

**자산 종류는 넷 중 하나로 정형화한다**
- `template` — 항목별 빈칸과 작성 예시를 나란히 놓은 양식. 2열 표로 만든다
  (왼쪽 항목명, 오른쪽 작성 예시). 그대로 복사해 채울 수 있어야 한다.
- `examples` — 상황별 예시 문장 3~5개. 각 항목에 "이렇게 말한다 / 이건 피한다"를
  대비시키면 좋다.
- `table` — 숫자·조건이 걸린 주제의 계산 예시나 기준 표.
- `checklist` — 순서대로 확인할 항목. <ol>로 쓴다.

**작성 규칙**
- 자산 앞에 h2 소제목을 달아 검색 쿼리와 맞춘다
  (예: "경력기술서 양식과 작성 예시", "퇴사 사유 답변 예시 문장").
- 표에는 최소한의 인라인 스타일만 준다:
  `<table style="width:100%;border-collapse:collapse">`,
  각 셀에 `style="border:1px solid #ddd;padding:8px"`.
- 자산은 결론 앞, 본문 중후반에 배치한다. 마지막 Q. 문단 뒤에 오면 안 된다.
- **자산 안에 지어낸 수치를 넣지 않는다.** 금액·요율이 걸린 표는 실제 기준을
  확인해야 하므로, 그 항목을 fact_check_notes에 반드시 남긴다.

## quote_cards 규칙
본문에서 가장 강한 문장 2개를 **그대로** 골라 넣는다. 새로 쓰지 않는다.
카드 이미지에 얹을 문장이라 45자 이내여야 하고, 단독으로 읽어도 완결돼야 한다.
설명형("~에 대해 알아보자")이 아니라 선언형이어야 한다.

## image_query 규칙
도입부에 넣을 사진을 무료 스톡에서 찾을 **영문** 검색어. 2~4단어.
사람 표정이 과장된 연출 사진이 걸리지 않게, 상황·사물 중심으로 쓴다.
좋은 예: "empty meeting room", "notebook desk morning"
나쁜 예: "happy businessman handshake"

## fact_check_notes 규칙
지어낸 수치는 절대 쓰지 않는다. 확신이 없는 사실은 본문에서
"~로 알려졌다" 같은 완충 표현으로 쓰고, 그 항목을 여기 반드시 남긴다.
이 목록은 사람이 발행 전에 확인할 체크리스트다."""


def _response_text(resp) -> str:
    """응답에서 text 블록만 이어붙인다.

    확장 사고(extended thinking)가 켜지면 content[0]이 ThinkingBlock일 수 있어서
    첫 블록을 그냥 집으면 깨진다.
    """
    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    if not parts:
        raise ValueError("응답에 텍스트 블록이 없습니다.")
    return "\n".join(parts)


BODY_MARKER = "===BODY==="


def _split_response(text: str) -> tuple[str, str]:
    """응답을 메타데이터 JSON과 본문 HTML로 가른다.

    본문을 JSON 문자열 안에 넣으면 표·따옴표가 많은 글에서 이스케이프가
    자주 깨진다. 마커로 분리하면 본문은 파싱을 아예 거치지 않는다.
    """
    if BODY_MARKER not in text:
        raise ValueError(f"{BODY_MARKER} 마커가 없습니다. 응답 앞부분: {text[:200]}")
    head, _, body = text.partition(BODY_MARKER)
    body = body.strip()
    # 모델이 본문을 코드펜스로 감쌌으면 벗긴다
    fence = re.match(r"^```(?:html)?\s*(.*?)\s*```$", body, re.S)
    if fence:
        body = fence.group(1).strip()
    if not body:
        raise ValueError("본문이 비어 있습니다.")
    return head, body


def _extract_json(text: str) -> dict:
    """모델이 코드펜스를 붙였거나 앞뒤에 말을 덧붙였어도 JSON을 건져낸다."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON을 찾지 못했습니다. 응답 앞부분: {text[:200]}")

    blob = text[start : end + 1]
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        # 본문 HTML에 줄바꿈이 그대로 들어오면 엄격 모드가 거부한다.
        # strict=False는 문자열 안의 제어문자를 허용한다.
        return json.loads(blob, strict=False)


MIN_CHARS = 3000


def body_length(body_html: str) -> int:
    """공백을 뺀 본문 글자수. 네이버·구글 노출 기준을 맞췄는지 확인용."""
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", body_html)))


def expand(client, draft: dict, topic: dict) -> dict:
    """본문이 짧으면 한 번 더 불러서 늘린다.

    새로 쓰게 하지 않고 기존 원고를 확장시킨다. 다시 쓰게 하면
    잘 나온 훅과 결론까지 같이 날아간다.
    """
    current = body_length(draft["body_html"])
    prompt = f"""아래는 '{topic['keyword']}' 주제로 쓴 초안 본문이다.
공백 제외 {current}자인데 {MIN_CHARS}자 이상이 필요하다. {MIN_CHARS - current}자를 더 채워야 한다.

{draft['body_html']}

이 원고를 {MIN_CHARS}자 이상으로 늘린다. 규칙은 이렇다.
- 훅(첫 문단)과 마지막 Q. 문단은 그대로 둔다.
- **표(<table>)나 양식 블록이 이미 있으면 지우거나 줄이지 않는다.** 그대로 살린다.
- 새 소제목(h2)을 2~3개 추가한다. 기존 섹션에도 구체적 사례·장면·수치를 덧붙인다.
- 분량을 채우려고 같은 말을 다르게 반복하지 않는다.
- 없는 수치를 지어내지 않는다.

늘린 본문 HTML만 답한다. JSON도, 코드펜스도, 설명도 붙이지 않는다."""

    resp = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    body = _response_text(resp).strip()
    # 확장은 본문만 돌려받으므로 파싱할 게 없다. 마커나 코드펜스만 벗긴다.
    if BODY_MARKER in body:
        body = body.split(BODY_MARKER, 1)[1].strip()
    fence = re.match(r"^```(?:html)?\s*(.*?)\s*```$", body, re.S)
    if fence:
        body = fence.group(1).strip()

    # 확장이 실패해 엉뚱한 답이 오면 원본을 지킨다
    if body_length(body) < current:
        print("  확장 결과가 더 짧아 원본을 유지합니다")
        return draft

    draft["body_html"] = body
    return draft


def build_prompt(topic: dict) -> str:
    if topic["track"] == "trend":
        context = "\n".join(f"- {h}" for h in topic["headlines"]) or "(연관 기사 없음)"
        return f"""오늘 구글 트렌드에 오른 키워드로 글을 쓴다.

키워드: {topic['keyword']}
검색 규모: {topic['traffic']}
연관 기사 헤드라인:
{context}

이 키워드를 {topic['category']} 관점에서 다룬다. 단순 뉴스 요약이 아니라,
25년차 마케터가 이 현상에서 읽어낸 구조를 쓴다. 뉴스가 다루지 않는 각도여야 한다."""

    return f"""오늘의 주제로 글을 쓴다.

주제: {topic['keyword']}
분류: {topic['category']}

검색해서 들어온 독자가 답을 얻고 가되, 정보 나열로 끝나지 않게 한다.
이선생 본인의 장면에서 출발해서 구조적 분석으로 착지한다."""


def write_draft(topic: dict) -> dict:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = build_prompt(topic)

    for attempt in (1, 2, 3):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            head, body = _split_response(_response_text(resp))
            draft = _extract_json(head)
            draft["body_html"] = body
            break
        except (ValueError, json.JSONDecodeError) as exc:
            if attempt == 3:
                raise
            print(f"  응답 파싱 실패, 재시도합니다 ({exc})")

    # 한 번에 목표를 못 채우는 경우가 있어 최대 두 번까지 늘린다.
    for _ in range(2):
        length = body_length(draft["body_html"])
        if length >= MIN_CHARS:
            break
        print(f"  본문 {length}자 → {MIN_CHARS}자 목표로 확장 중")
        draft = expand(client, draft, topic)
    print(f"  최종 본문 {body_length(draft['body_html'])}자")

    draft["topic"] = topic
    return draft
