# -*- coding: utf-8 -*-
"""묶음 생성이 이미 끝났으면 건너뛴다.

세션에서 띄운 실행과 스케줄러 작업이 겹쳐 두 번 생성되는 것을 막는다.
목표 개수만큼 이미 있으면 종료 코드 1을 돌려주고, 배치 파일이 이를 보고 멈춘다.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

target = Path(os.environ.get("OUTPUT_DIR", "output"))
want = int(os.environ.get("DRAFTS_PER_DAY", "10"))
have = len(list(target.rglob("*.html"))) if target.exists() else 0

print(f"이미 생성된 초안: {have}건 / 목표 {want}건")
sys.exit(1 if have >= want else 0)
