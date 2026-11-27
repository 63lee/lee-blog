# -*- coding: utf-8 -*-
"""초안 → 사용자 검사 → 이미지 의 두 단계 작업에서 쓰는 초안 파일 (2026-11-27).

사용자: "초안까지 작성하고 나한테 검사받고 이미지 만드는 게 좋겠어" (직장생활·브랜드시선 둘 다).
자동 실행은 글만 쓰고 원고 폴더에 아래 두 파일을 둔다.
  00_초안_검사용.txt : 사용자가 읽고 직접 고치는 파일
  _초안정보.json      : 이미지 단계에 필요한 나머지 (사진 자리 설명, 공식 페이지, 출처 …)
검사가 끝나면 'python office.py finish 폴더' / 'python brand.py --finish 폴더' 가
고친 초안을 읽어 사진·썸네일·클립·최종 원고(00_네이버용_원고.html/txt)를 같은 폴더에 만든다.

초안 파일 형식 (--- 줄로 나눈다):
  제목
  (다른 제목 후보) …
  ---
  본문: '## 소제목', '[사진1]' 한 줄, '· 목록', 문장마다 줄바꿈, 문단 사이 빈 줄
  ---
  #해시태그 …
  ---
  참고 (사진 자리 설명, 발행 전 확인, 출처) — 이미지 단계에서는 읽지 않는다
"""
import html
import json
import re
from pathlib import Path

DRAFT = "00_초안_검사용.txt"
INFO = "_초안정보.json"
GUIDE = "(검사하면서 이 파일을 직접 고쳐도 됩니다. --- 줄은 지우지 마세요. 다 되면 Claude 에게 이미지 만들어 달라고 하면 됩니다.)"


def write(folder: Path, title: str, alts: list, body: str, hashtags: list, notes: list, info: dict) -> list:
    folder.mkdir(parents=True, exist_ok=True)
    head = [title, ""]
    if alts:
        head += ["(다른 제목 후보)"] + [f"- {t}" for t in alts] + [""]
    text = "\n".join(head + [GUIDE, "---", body.strip(), "---", " ".join(hashtags), "---"] + notes) + "\n"
    a, b = folder / DRAFT, folder / INFO
    a.write_text(text, encoding="utf-8")
    b.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return [a, b]


def read(folder: Path) -> dict:
    parts = re.split(r"\n-{3,}\s*\n", (folder / DRAFT).read_text(encoding="utf-8").replace("\r\n", "\n"))
    head = [l for l in parts[0].splitlines() if l.strip()]
    title = head[0].strip()
    alts = [l[2:].strip() for l in head if l.startswith("- ")]
    body = parts[1].strip() if len(parts) > 1 else ""
    tags = re.findall(r"#\S+", parts[2]) if len(parts) > 2 else []
    info = json.loads((folder / INFO).read_text(encoding="utf-8")) if (folder / INFO).exists() else {}
    return {"title": title, "alts": alts, "body": body, "hashtags": tags, "info": info}


def body_to_html(body: str) -> str:
    """초안 본문(줄글) → 네이버 붙여넣기용 HTML. 문단 안 줄바꿈은 <br>, '## ' 는 <h3>."""
    out, para = [], []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(html.escape(l) for l in para) + "</p>")
            para.clear()
    for line in body.splitlines():
        s = line.strip()
        if not s:
            flush()
        elif s.startswith("## "):
            flush()
            out.append(f"<h3>{html.escape(s[3:])}</h3>")
        elif re.fullmatch(r"\[사진\d+\]", s):
            flush()
            out.append(f"<p>{s}</p>")
        else:
            para.append(s)
    flush()
    return "\n".join(out)


def html_to_body(body_html: str) -> str:
    """모델이 HTML 로 준 본문을 초안 줄글로."""
    t = re.sub(r"<h3[^>]*>(.*?)</h3>", lambda m: "\n## " + m.group(1).strip() + "\n", body_html, flags=re.S)
    t = re.sub(r"<li[^>]*>", "· ", t)
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"</(p|li|ul)>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = "\n".join(l.strip() for l in t.splitlines())
    return re.sub(r"\n{3,}", "\n\n", t).strip()
