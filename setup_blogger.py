# -*- coding: utf-8 -*-
"""최초 1회 실행: 구글 로그인하고 blogId를 알아낸다."""
import sys

from publisher import find_blog_id

BLOG_URL = "https://63lee.blogspot.com/"

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else BLOG_URL
    print(f"브라우저가 열립니다. 구글 계정으로 로그인하고 권한을 허용하세요.\n대상 블로그: {url}\n")
    blog_id = find_blog_id(url)
    print(f"\n연결 성공.\n\n  .env 파일에 아래 줄을 넣으세요:\n\n  BLOG_ID={blog_id}\n")
