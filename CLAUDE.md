# lee-blog 작업 메모

이 저장소는 '역삼동 이선생' 블로그 자동화다. **호텔아로하(Hotel Aroha) 작업은 이 저장소가 아니다.**
아로하 요청이 오면 아래를 먼저 읽고, 이미 있는 것을 새로 만들지 않는다.

## 아로하 릴스 (2026-11-20 확인)

- 릴스는 별도 저장소 `arohajejuhotel/aroha-blog` 가 **매일 자동**으로 만든다.
  - 워크플로: `.github/workflows/daily-reel.yml` (매일 04:13 KST, 수동 실행 `workflow_dispatch` 가능)
  - 코드: `src/reel_daily.py`(장소 선정·자막), `src/reels.py`(영상 조립), `src/insta_reels.py`, `src/insta_cta.py`
  - 기록: `state/reels.json` (날짜·장소·키워드·Drive 폴더)
- 수동으로 만들 때는 GitHub Actions 에서 `Daily reel` 실행 → `place`(예: 성산일출봉), `keyword`(예: 제주 일출 명소) 입력.
  이 세션들은 해당 저장소에 읽기 전용이라 직접 실행할 수 없다. 사용자가 Actions 화면에서 실행한다.
- 결과물은 구글 드라이브 `아로하 릴스/날짜 [릴스] 제목/` 폴더에 저장된다.
  - `reel_instagram.mp4`, `reel_xiaohongshu.mp4`, `caption_instagram.txt`, `caption_naver.txt`, `caption_xiaohongshu.txt`
  - 올리는 건 사람이 한다. 음악은 앱에서 넣는다.
- 만든 소재 (2026-11-16 까지): 따라비오름, 용눈이오름, 제주해녀박물관, 위미동백나무군락, 휴애리,
  아부오름, 섭지코지, 비자림, 혼인지, 우도, 카멜리아힐, 공항 기념품 샌드, 광치기해변, 쇠소깍,
  성읍민속마을, 감귤박물관, 김녕해수욕장. 같은 장소를 다시 만들기 전에 `state/reels.json` 을 본다.
- 기록에 빈 날짜: 11/11, 11/13, 11/14. 원인은 Actions 로그로 확인해야 한다 (미확인).
- 호텔 소개 릴스(오션뷰호텔·패밀리객실·디럭스더블)와 손님 이야기 릴스(노부부·러시아 동전)는 위 자동화와 별개로 만든 것이다.

## 아로하 작업 시 주의

- 호텔 사진은 구글 드라이브에 있고 bash 에서 직접 못 읽는다. Drive 커넥터로 받는다.
- 검증된 사실(요금·거리·시간)은 `hotel-aroha` 스킬에 있다. 지어낸 일화·수치 금지.
- 이 저장소의 `clip.py`, `info_clip.py` 등은 이선생 블로그용이다. 아로하 릴스에 쓰지 않는다.
