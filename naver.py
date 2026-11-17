# -*- coding: utf-8 -*-
"""네이버 블로그에 붙여넣을 '네이버용 버전'을 만든다 (2026-10-16).

같은 글을 그대로 붙여넣으면 네이버 유사문서 필터에 걸려 검색에서 빠질 수 있다.
그래서 같은 주제를 네이버 말투·구성으로 다시 쓰고(문장 재사용 금지), 원문 링크를 단다.
결과물은 구글 드라이브 '네이버용 블로그 글/{blog}/날짜 제목' 폴더에 저장한다:
  - 00_네이버용_원고.html : 브라우저로 열어 전체 복사 → 네이버 에디터에 붙여넣기 (서식 유지)
  - 00_네이버용_원고.txt  : 서식 없는 버전
  - 01_썸네일.jpg/png, 02~ 사진 : 원고의 [사진n] 자리에 넣을 사진
"""
import html
import re
import shutil
from pathlib import Path

import cliche

# 2026-11-17 사용자: "네이버가 중복글로 인식하는 거 같아 … 다르게 써"
# 예전엔 구글 본문을 통째로 주고 '다시 쓰라'고 해서 구성·예시·문장 흐름이 비슷하게 남았다.
# 이제 구글 본문은 주지 않는다. 사실(숫자·법 조항·기준)만 따로 뽑아 주고, 네이버 글은 다른 각도로 처음부터 쓴다.
FACTS_PROMPT = """아래 글에서 사실 정보만 뽑는다: 숫자, 금액, 기간, 법 조항, 기관 이름, 신청 절차, 기준 연도.
의견·장면·예시·비유·문장 표현은 뽑지 않는다. 한 줄에 하나, '- ' 로 시작, 최대 10줄.

{body}"""

PROMPT = """네이버 블로그 글을 **처음부터** 쓴다. 같은 주제로 구글 블로그에 다른 글이 이미 있다.
네이버는 웹에 이미 있는 글과 비슷하면 유사문서로 보고 검색에서 뺀다. 그래서 구글 글과 겹치지 않는 글이어야 한다.

[주제] {title}
[핵심 검색어] {keyword}
[구글 글 주소] {url}
[쓸 수 있는 사실 — 필요한 것만 골라 쓴다]
{facts}

[구글 글과 다르게 만드는 규칙]
- 제목은 구글 제목 '{title}'과 다른 말로 짓는다. 핵심 검색어는 앞쪽에 둔다. 25~35자.
- 각도: 구글 글은 정보 정리형이다. 네이버 글은 **이선생 한 사람의 이야기**다 —
  이선생이 직접 겪은 하루(또는 후배와 나눈 대화) 한 장면을 처음부터 끝까지 따라가며, 사실은 그 이야기 속에서 필요한 만큼만 꺼낸다.
- 구성: 소제목 3~4개, 표 쓰지 않는다. 목록은 한 번만. 구글 글에 흔히 들어가는 '정의 문장', 'FAQ', '체크리스트'는 쓰지 않는다.
- 이선생의 감정(당황, 미안함, 뿌듯함 등)을 솔직하게 한두 번 쓴다.
- 짧은 문단(2~3문장), 소제목은 굵게. 이모지는 소제목에만 가끔.
- 분량 1,500~2,300자.
- 사진 자리는 [사진1]~[사진{n}] 로 표시한다 (사진은 {n}장. 1번은 썸네일이라 맨 위, 나머지는 이선생 사진).
- 마지막 문단 바로 앞에 "숫자와 절차를 표로 정리한 글은 여기" 같은 말로 구글 글 주소를 한 번만 안내한다.
- 해시태그 10~15개 (네이버에서 실제로 검색되는 붙여쓴 단어).
{extra}
아래 세 태그만 이 순서로 출력한다 (JSON 아님, 다른 말 없이):
<title>제목</title>
<body><p>, <h3>, <ul>, <li>, <strong> 만 쓴 본문</body>
<hashtags>#태그1 #태그2 ...</hashtags>"""


def _plain(body_html: str) -> str:
    t = re.sub(r"<script.*?</script>", "", body_html, flags=re.S)
    t = re.sub(r"<(br|/p|/h[1-6]|/li)[^>]*>", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(re.sub(r"<[^>]+>", "", t))).strip()


OVERLAP_LIMIT = 0.12


def overlap(a: str, b: str) -> float:
    """b 의 글자 6개 묶음 중 a 에도 있는 비율. 문장을 그대로 옮기거나 살짝 바꾼 정도를 잡는다."""
    def grams(t):
        t = re.sub(r"\s+", "", t)
        return {t[i:i + 6] for i in range(len(t) - 5)}
    ga, gb = grams(a), grams(b)
    return len(ga & gb) / len(gb) if gb else 0.0


def _facts(client, model: str, text: str) -> str:
    try:
        resp = client.messages.create(model=model, max_tokens=3000, messages=[
            {"role": "user", "content": FACTS_PROMPT.format(body=text[:9000])}])
        out = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        return "\n".join(l for l in out.splitlines() if l.strip().startswith("-")) or "(없음)"
    except Exception as exc:
        print(f"  [경고] 사실 뽑기 실패 ({type(exc).__name__})")
        return "(없음)"


def write(client, model: str, title: str, keyword: str, url: str, body_html: str,
          n_photos: int, extra: str = "") -> dict:
    google_text = _plain(body_html)
    facts = _facts(client, model, google_text)
    prompt = PROMPT.format(title=title, keyword=keyword or title, url=url or "(주소 미정)",
                           facts=facts, n=n_photos, extra=extra)
    # 본문 HTML 에 따옴표가 섞여 JSON 이 깨진 적이 있어(2026-10-17) 태그로 나눠 받는다. 한 번 더 시도한다.
    prompt += "\n\n" + cliche.RULE
    for _ in range(2):
        resp = client.messages.create(model=model, max_tokens=6000,
                                      messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        parts = {k: re.search(rf"<{k}>(.*?)</{k}>", text, re.S) for k in ("title", "body", "hashtags")}
        if parts["title"] and parts["body"]:
            tags = parts["hashtags"].group(1) if parts["hashtags"] else ""
            post = {"title": parts["title"].group(1).strip(),
                    "body_html": parts["body"].group(1).strip(),
                    "hashtags": re.findall(r"#\S+", tags)}
            post = cliche.scrub_fields(client, model, post, ("title", "body_html"))
            ov = overlap(google_text, _plain(post["body_html"]))
            print(f"  네이버용 원고와 구글 글 겹침 {ov:.0%}")
            if ov <= OVERLAP_LIMIT or _ == 1:
                if ov > OVERLAP_LIMIT:
                    print("  [경고] 네이버용 원고가 구글 글과 많이 겹칩니다. 올리기 전에 손봐 주세요.")
                return post
            prompt += (f"\n\n[다시 쓰기] 방금 쓴 글이 구글 글과 문장이 {ov:.0%} 겹쳤다. "
                       "표현과 장면을 완전히 바꿔 다시 쓴다.")
            continue
    raise ValueError(f"네이버용 원고 형식을 읽지 못함: {text[:200]!r}")


def package(post: dict, photos: list, out_dir: Path) -> list:
    """원고(html/txt)와 사진을 out_dir 에 모으고 파일 목록을 돌려준다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for i, src in enumerate(photos, 1):
        src = Path(src)
        dst = out_dir / (f"{i:02d}_썸네일{src.suffix}" if i == 1 else f"{i:02d}_사진{i}{src.suffix}")
        shutil.copyfile(src, dst)
        files.append(dst)

    tags = " ".join(post.get("hashtags", []))
    body = post["body_html"]
    # [사진n] 표시는 눈에 띄게 (붙여넣은 뒤 그 자리에 사진을 넣는다)
    body = re.sub(r"\[사진(\d+)\]",
                  lambda m: f'<p style="background:#fff3cd;padding:6px 10px;">📷 [사진{m.group(1)}] '
                            f'← {int(m.group(1)):02d}번 사진을 여기에</p>', body)
    page = (f"<!doctype html><meta charset='utf-8'><title>{html.escape(post['title'])}</title>"
            f"<div style='max-width:720px;margin:30px auto;font:16px/1.8 sans-serif'>"
            f"<p style='color:#888;font-size:13px'>아래 제목과 본문을 복사해 네이버 블로그에 붙여넣으세요. "
            f"노란 표시 자리에 같은 번호의 사진을 넣으면 됩니다.</p>"
            f"<h2>{html.escape(post['title'])}</h2>{body}<p>{html.escape(tags)}</p></div>")
    h = out_dir / "00_네이버용_원고.html"
    h.write_text(page, encoding="utf-8")
    t = out_dir / "00_네이버용_원고.txt"
    t.write_text(f"{post['title']}\n\n{_plain(post['body_html'])}\n\n{tags}\n", encoding="utf-8")
    return [h, t] + files
