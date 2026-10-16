# -*- coding: utf-8 -*-
"""Blogger API v3로 초안(draft)을 올린다. 발행은 하지 않는다."""
import os
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/blogger"]
BASE = Path(__file__).parent
TOKEN_PATH = BASE / "token.json"
CLIENT_SECRET_PATH = BASE / "client_secret.json"

# Blogger는 짧은 시간에 글을 여러 개 만들면 429를 주고, 계속하면 403으로 막는다.
# 한 번 막히면 몇 시간 풀리지 않으므로 넉넉하게 간격을 둔다.
MIN_INTERVAL_SEC = 15
BACKOFF_SEC = (30, 90, 240)

_last_write = 0.0


def _throttle() -> None:
    """직전 쓰기 호출과 최소 간격을 둔다."""
    global _last_write
    wait = MIN_INTERVAL_SEC - (time.monotonic() - _last_write)
    if wait > 0:
        time.sleep(wait)
    _last_write = time.monotonic()


def _env_credentials():
    """GitHub Actions 처럼 파일이 없는 곳에서는 환경 변수의 refresh token 으로 인증한다."""
    token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()
    cid = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not (token and cid and secret):
        return None
    creds = Credentials(None, refresh_token=token, client_id=cid, client_secret=secret,
                        token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES)
    creds.refresh(Request())
    return creds


def get_service():
    env_creds = _env_credentials()
    if env_creds:
        return build("blogger", "v3", credentials=env_creds)

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                raise FileNotFoundError(
                    f"{CLIENT_SECRET_PATH} 가 없습니다. README의 'Blogger 연결' 단계를 먼저 진행하세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return build("blogger", "v3", credentials=creds)


def find_blog_id(blog_url: str) -> str:
    """블로그 주소로 blogId를 찾는다. 최초 1회 설정용."""
    return get_service().blogs().getByUrl(url=blog_url).execute()["id"]


def is_draft_mode() -> bool:
    """PUBLISH_MODE=publish 면 바로 공개 발행, 그 외(기본)는 초안."""
    return os.environ.get("PUBLISH_MODE", "draft").strip().lower() != "publish"


def _insert(blog_id: str, title: str, body_html: str, labels: list[str]) -> dict:
    _throttle()
    return (
        get_service()
        .posts()
        .insert(
            blogId=blog_id,
            isDraft=is_draft_mode(),
            body={"kind": "blogger#post", "title": title, "content": body_html, "labels": labels},
        )
        .execute()
    )


def create_draft(title: str, body_html: str, labels: list[str]) -> dict:
    """Blogger 에 올린다. PUBLISH_MODE=publish 면 바로 공개, 아니면 초안(사람이 발행).

    429는 속도 제한이라 기다렸다 다시 시도한다.
    403은 권한·할당량 문제라 기다려도 안 풀리므로 바로 포기한다.
    400은 대개 라벨이 문제라서, 라벨을 줄여가며 살려본다.
    """
    blog_id = os.environ.get("BLOG_ID")
    if not blog_id:
        raise RuntimeError("BLOG_ID 환경변수가 비어 있습니다. .env를 확인하세요.")

    for i, wait in enumerate((0,) + BACKOFF_SEC):
        if wait:
            print(f"    속도 제한, {wait}초 대기 후 재시도 ({i}/{len(BACKOFF_SEC)})")
            time.sleep(wait)
        try:
            return _insert(blog_id, title, body_html, labels)
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status == 429:
                continue  # 진짜 속도 제한 — 더 기다린다
            if status == 403:
                # Blogger의 권한 거부는 본문에 'PERMISSION_DENIED'가 아니라
                # reason "forbidden" / "The caller does not have permission"으로 온다.
                # 기다려도 풀리지 않으므로 재시도하지 않는다. 재시도하면 글마다 6분씩 헛돈다.
                raise RuntimeError(
                    "Blogger가 쓰기를 거부했습니다(403 forbidden). 읽기는 되는데 쓰기만 "
                    "막히는 경우라 권한·할당량 문제입니다. 기다려도 풀리지 않습니다."
                ) from exc
            if status == 400 and labels:
                # 라벨을 절반으로, 그래도 안 되면 없이 올린다. 본문이 우선이다.
                for fallback in (labels[: len(labels) // 2], []):
                    try:
                        post = _insert(blog_id, title, body_html, fallback)
                        print(f"    라벨 {len(labels)}개 → {len(fallback)}개로 줄여 등록")
                        return post
                    except HttpError:
                        continue
            raise

    raise RuntimeError(
        "Blogger가 계속 속도 제한을 반환합니다. 몇 시간 뒤에 다시 시도하세요."
    )
