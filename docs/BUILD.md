# 재빌드

## 준비
- Python 3.13, `pip install pillow capstone pycdlib zstandard`
- 같은 폴더에 원본 ISO `Ratchet & Clank (Japan).iso`(해시는 README 참고)와 `NanumSquareNeo-cBd.ttf`, `NanumSquareNeo-dEb.ttf`
  - 저장소 폴더의 **상위 폴더**를 기본으로 찾습니다. 다른 곳이면 환경변수 `RC_ISO`(원본 ISO 경로), `RC_FONTS`(글꼴 폴더), `RC_OUT`(결과 ISO 경로)로 지정합니다.

## 순서
```
python tools/dump.py       # WAD 압축 해제 캐시 (cache/, 약 830MB, 10분 내외)
python tools/prepare.py    # ELF·원본 폰트·원문 목록 생성 (text/, lv/)
python tools/movie_extract.py   # 동영상·음성 추출 (movie/orig, movie/wav)
python tools/movie_asr.py       # (선택) 받아쓰기 -> movie/asr/*.json (pip install faster-whisper)
python tools/movie_sub.py       # movie/subs/*.tsv 로 자막 합성 -> movie/enc/*.PSS (pip install av imageio-ffmpeg numpy)
python tools/movie_check.py     # 동영상 타이밍·화질 검사 (문제 0 이어야 함)
python tools/build.py      # 결과 ISO 생성
python tools/verify.py     # 결과 ISO 전수검사 (총 오류 0 이어야 함)
```
결과는 README 의 결과 ISO SHA-256 과 같아야 합니다.

## 번역 파일
번역 대본(`translation/`)은 저장소에 포함하지 않습니다(RIGHTS.md 참고). 아래 형식의 파일을 직접 준비하면 빌드할 수 있습니다.

- `translation/ko/*.tsv`: `번호<TAB>번역` (번호는 `text/src_all.tsv` 의 원문 번호). 제어 코드 `{0C}…{08}`(강조), `{01}`(줄바꿈), `{10}~{19}`(버튼)는 원문과 같게 둡니다.
- `translation/scene_ko/*.tsv`: 컷신 자막 (`text/scene_src.tsv` 번호).
- `translation/cards_ko.tsv`: 컷신 타이틀 카드 17장.
- `movie/subs/V###.tsv`: 동영상 자막 `시작초<TAB>끝초<TAB>자막` (`
` 으로 줄바꿈). ffmpeg 버전이 다르면 재인코딩 바이트가 달라져 결과 해시가 배포판과 다를 수 있습니다.
- 새 음절이 늘어 글꼴 용량(2바이트 840자 + 1바이트 40자)을 넘으면 빌드가 멈춥니다.
