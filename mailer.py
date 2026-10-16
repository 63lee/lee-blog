# -*- coding: utf-8 -*-
"""Blogger '이메일로 게시' 로 글을 올린다.

이 계정은 Blogger API 글쓰기가 403 으로 막혀 있다 (웹에서는 됨, 2026-10).
그래서 Blogger 의 비밀 이메일 주소로 메일을 보내 글을 만든다.
- 메일 제목 → 글 제목, HTML 본문 → 글 내용
- 즉시 게시/초안 여부는 Blogger 설정(이메일로 게시)에서 정한다
- 라벨은 메일로 붙일 수 없다
- <script>(JSON-LD)는 Blogger 가 지우므로 미리 뺀다
- 이미지는 저장소(jsDelivr) 주소로 본문에 들어 있어 첨부할 필요가 없다

필요한 환경 변수: BLOGGER_POST_EMAIL, GMAIL_ADDRESS, GMAIL_APP_PASSWORD
"""
import os
import re
import smtplib
import time

import urllib.request
import json
from email.header import Header
from email.mime.text import MIMEText


def enabled() -> bool:
    return os.environ.get("POST_VIA", "").strip().lower() == "email"


def send(title: str, body_html: str) -> dict:
    to = os.environ["BLOGGER_POST_EMAIL"].strip()
    sender = os.environ["GMAIL_ADDRESS"].strip()
    password = re.sub(r"\s+", "", os.environ["GMAIL_APP_PASSWORD"])

    html = re.sub(r"<script.*?</script>", "", body_html, flags=re.S)
    msg = MIMEText(f"<html><body>{html}</body></html>", "html", "utf-8")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = sender
    msg["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(sender, password)
        smtp.sendmail(sender, [to], msg.as_string())
    return {"via": "email", "title": title}


def wait_published(title: str, blog_url: str = "https://63lee.blogspot.com", minutes: int = 5) -> str:
    """공개 피드에 글이 나타날 때까지 기다렸다가 주소를 돌려준다. 못 찾으면 빈 문자열."""
    feed = f"{blog_url}/feeds/posts/default?alt=json&max-results=5"
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        try:
            data = json.loads(urllib.request.urlopen(feed, timeout=20).read())
            for e in data.get("feed", {}).get("entry", []):
                if e["title"]["$t"].strip() == title.strip():
                    return next(l["href"] for l in e["link"] if l["rel"] == "alternate")
        except Exception:
            pass
        time.sleep(20)
    return ""
