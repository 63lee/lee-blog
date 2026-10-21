# -*- coding: utf-8 -*-
"""블로그 글 → 네이버 클립·인스타 릴스 대본(JSON) (2026-10-20).

사용자와 샘플 3편(회식·퇴사 사유·사내정치)을 다듬으며 정한 규칙을 프롬프트로 옮겼다.
  - 기승전결이 보이게 장면을 잇는다 (주요 문장을 뽑아 나열하면 흐름이 어색하다)
  - 화면 하나에 의미 덩어리 하나, 두 줄 자막. 자막과 내레이션은 같은 문장
  - 배경은 사람 얼굴 없는 사물·공간 (스톡 인물은 연출 티가 나서 낯설다)
  - AI 상투 표현 금지 (cliche.RULE)
만든 JSON 은 clip.build() 가 그대로 읽는다.
"""
import json
import re

import cliche

PROMPT = """아래 블로그 글로 네이버 클립(인스타 릴스 겸용) 60초 안팎 세로 영상 대본을 만든다.
글쓴이는 회사 생활을 오래 한 직장 선배 '역삼동이선생'(여성)이고, '25년' 같은 경력 연수는 말하지 않으며, 평어체(~다, ~한다)로 말한다.

[글 제목] {title}
[글 본문]
{body}

규칙
1. 흐름: 기승전결이 분명해야 한다. 글의 주요 문장을 뽑아 나열하지 말고, 앞 장면을 받아 다음 장면으로
   넘어가게 쓴다. "그런데", "그래서", "그렇다고" 같은 연결어를 장면 첫머리에 적절히 쓴다.
   - 기(1장면): 글 속 실제 장면·대사로 시작하는 훅. 첫 화면에서 멈추게 만든다.
   - 승(2~3장면): 무슨 뜻인지 풀고, 글의 비유가 있으면 살린다.
   - 전(2장면): 흔한 생각을 뒤집거나 반론에 답한다.
   - 결(1~2장면): 글의 결론을 담백하게 닫는다.
2. 장면은 7~8개. 장면마다 subs(자막 화면) 2~3개.
   - 자막 화면 하나 = 의미 덩어리 하나. 길면 "\\n" 으로 두 줄로 나눈다. 한 줄은 15자 안팎(최대 17자).
   - 줄은 의미 단위로 나눈다. 줄 머리에 '수, 것, 게, 때, 뿐' 같은 말이 오면 안 된다.
     좋은 예: "이 사람과 3년을\\n같이 일할 수 있을지 보는 거다"  나쁜 예: "이 사람과 3년을 일할\\n수 있을지 본다"
   - 대사·인용은 “ ” 로 감싼다.
   - 글에 없는 사실·숫자·일화를 지어내지 않는다.
3. em: 장면에서 강조색으로 칠할 낱말 1개(자막에 그대로 들어 있는 부분 문자열). 없으면 빈 배열.
   2~6자짜리 핵심 낱말(예: "적금", "70%", "두 번째 질문")이면 화면 가운데 아주 크게 띄우는 화면으로 쓰여
   리듬이 생긴다. 장면 절반 정도에 이런 짧은 강조어를 둔다. 대사·인용 자막은 따로 큰 명조 화면이 된다.
4. query: 배경 영상을 Pixabay 에서 찾을 영어 검색어 2~4단어. **사람 얼굴이 나오지 않는 사물·공간·손**
   위주로 장면의 비유나 분위기에 맞춘다 (예: "sticky notes whiteboard", "piggy bank coins",
   "network cables", "chess pieces board", "coffee cup desk morning"). 침실·속옷·해변·항공뷰는 쓰지 않는다.
5. title: 화면 위에 계속 떠 있는 제목 3줄 (줄당 8자 안팎, 명조로 크게 쓴다). 마지막 줄이 강조색이다.
   질문형이나 대비형이 좋다 (예: ["사내정치,", "칭찬일까", "흠일까"], ["퇴사 사유,", "진실보다", "방향을 말한다"]).
6. end_line: 마지막 화면에서 블로그로 안내하는 한 줄 (예: "상황별로 바꿔 말하는 문장은"). end_say: 그 화면 내레이션
   (예: "상황별로 바꿔 말하는 문장은, 블로그 글에 표로 정리해 뒀다.").
7. caption: 네이버 클립 캡션. 3~4줄 요약 + "연결된 블로그 글에 정리해 뒀다" + 댓글을 부르는 질문 1개 + 해시태그 8~9개
   (#역삼동이선생 #슬기로운직장생활 포함).
   caption_instagram: 인스타 릴스 캡션. 핵심 2줄 + "프로필 링크의 블로그 글" 안내 + 저장 유도 1줄 + 질문 1개 + 해시태그 6~7개.

[흐름이 좋은 예 — 사용자와 다듬은 '사내정치' 클립. 장면 = 자막 화면들]
기  “그 친구, 일도 잘하지만 정치도 좀 해” / 칭찬 같기도 하고 흠 같기도 한 말이다
승  그런데 뜯어보면 칭찬에 가까운 말이다 / 사람 사이에서 일이 굴러가게 만든다는 뜻이니까
승  회사에서는 좋은 의견도 저절로 채택되지 않는다 / 누가 결정하고, 누가 실행하고, 누가 부담을 느끼는지 알아야 한다
승  그래서 정치는 회사 와이파이와 비슷하다 / 원하든 원하지 않든 출근하는 순간 연결돼 있다
전  “저는 정치 안 하고 실력으로 승부합니다” / 그 마음은 이해한다 / 그런데 좋은 보고서도 읽는 사람이 없으면 그냥 PDF다
전  그렇다고 아부와 같은 건 아니다 / 그 사람이 다녀간 뒤 문제가 더 분명해지는지 보면 안다
결  오래 신뢰받는 사람에게는 ‘같이 일해도 괜찮다’는 믿음이 있다 / 그 믿음은 적금처럼 평소에 조금씩 쌓인다
결  “그 사람과 이야기하면 막혔던 일이 풀려” / 그 정도의 정치라면 기꺼이 칭찬이다
→ 장면마다 앞 장면의 말을 받아서 잇는다. 같은 내용을 두 번 말하지 않는다. 결론은 처방이 아니라 생각할 거리로 닫는다.

{cliche_rule}

다음 JSON 하나만 출력한다 (코드펜스 없이):
{{"title": ["", "", ""], "end_line": "", "end_say": "",
  "scenes": [{{"subs": ["", ""], "em": [""], "query": ""}}],
  "caption": "", "caption_instagram": ""}}"""


def _plain(body_html: str) -> str:
    t = re.sub(r"<(script|style|table).*?</\1>", " ", body_html, flags=re.S)
    t = re.sub(r"<(br|/p|/h[1-6]|/li)[^>]*>", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"<[^>]+>", "", t)).strip()


def _say(subs: list) -> str:
    """자막을 내레이션으로 잇는다. 화면마다 마침표를 넣어야 TTS 가 숨을 쉰다."""
    parts = []
    for s in subs:
        x = re.sub(r"[“”‘’\"]", "", s.replace("\n", " ")).strip()
        parts.append(x if x[-1:] in ".?!" else x + ".")
    return " ".join(parts)


def make_job(client, model: str, title: str, body_html: str) -> dict:
    prompt = PROMPT.format(title=title, body=_plain(body_html)[:7000], cliche_rule=cliche.RULE)
    last = None
    for _ in range(2):
        resp = client.messages.create(model=model, max_tokens=16000,
                                      messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        try:
            job = json.loads(text[text.index("{"): text.rindex("}") + 1])
            if len(job.get("scenes", [])) >= 5 and len(job.get("title", [])) >= 2:
                break
        except ValueError as exc:
            last = exc
    else:
        raise ValueError(f"클립 대본을 읽지 못함: {last}")

    for sc in job["scenes"]:
        sc["subs"] = [s.strip() for s in sc.get("subs", []) if s.strip()]
        cliche.scrub_fields(client, model, sc, ("subs",), "평어체")
        sc["em"] = [e for e in sc.get("em", []) if e and any(e in s for s in sc["subs"])]
        sc["say"] = _say(sc["subs"])
    job["scenes"] = [sc for sc in job["scenes"] if sc["subs"]]
    job["scenes"].append({"say": job.get("end_say") or f"{job.get('end_line', '')}, 블로그 글에 정리해 뒀다.",
                          "query": "", "end": True})
    cliche.scrub_fields(client, model, job, ("caption", "caption_instagram"), "평어체")
    job.update({"voice": "ko-KR-SunHiNeural", "rate": "+14%", "end_style": "link"})
    return job
