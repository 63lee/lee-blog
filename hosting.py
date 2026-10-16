# -*- coding: utf-8 -*-
"""글에 넣을 이미지를 GitHub 저장소에 올리고, 바로 쓸 수 있는 주소를 돌려준다.

Blogger API 에는 이미지 업로드가 없다. 그래서 이미지를 저장소(images/날짜/...)에
커밋·푸시하고, 커밋 해시로 고정된 jsDelivr 주소를 글에 넣는다.
jsDelivr 는 푸시 직후 바로 열리므로 GitHub Pages 배포를 기다릴 필요가 없다.
"""
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent


def enabled() -> bool:
    """IMAGE_HOSTING=github 일 때만 동작한다 (GitHub Actions 에서 켬)."""
    return os.environ.get("IMAGE_HOSTING", "").strip().lower() == "github"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=lee-blog-bot", "-c", "user.email=actions@github.com", *args],
        cwd=BASE, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _repo_slug() -> str:
    slug = os.environ.get("GITHUB_REPOSITORY")
    if slug:
        return slug
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", _git("remote", "get-url", "origin"))
    return m.group(1)


def publish(paths: list[Path], message: str) -> dict:
    """파일들을 한 번에 커밋·푸시하고 {경로: 주소} 를 돌려준다."""
    rels = [p.resolve().relative_to(BASE.resolve()).as_posix() for p in paths]
    _git("add", *rels)
    _git("commit", "-m", message)
    for _ in range(3):
        try:
            _git("push", "origin", "HEAD")
            break
        except subprocess.CalledProcessError:
            _git("pull", "--rebase", "origin", "main")
    else:
        raise RuntimeError("이미지 푸시 실패")
    sha = _git("rev-parse", "HEAD")
    slug = _repo_slug()
    # 한글 파일명을 그대로 두면 크롤러·썸네일 추출이 실패할 수 있어 퍼센트 인코딩한다
    urls = {p: f"https://cdn.jsdelivr.net/gh/{slug}@{sha}/{urllib.parse.quote(rel)}"
            for p, rel in zip(paths, rels)}

    # 첫 번째 파일이 열릴 때까지 잠깐 기다린다 (보통 몇 초)
    first = next(iter(urls.values()), None)
    for _ in range(12):
        try:
            if first and urllib.request.urlopen(first, timeout=15).status == 200:
                break
        except Exception:
            pass
        time.sleep(5)
    return urls
