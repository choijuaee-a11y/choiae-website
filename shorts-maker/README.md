# 블로그 → 쇼츠 자동 생성기

네이버 블로그 주소를 넣으면 AI가 글을 읽고 **세로형 쇼츠 영상(1080×1920, 30~50초)** 을 만들어 줍니다.
유튜브 쇼츠, 인스타 릴스, 틱톡에 바로 올릴 수 있어요.

```
블로그 주소 ─▶ ① 글·사진 가져오기 ─▶ ② Claude가 쇼츠 대본 작성 ─▶ ③ AI 음성(TTS) ─▶ ④ 자막·사진 합성 ─▶ shorts.mp4
```

- **글 가져오기**: 제목, 본문, 사진을 자동으로 수집 (스티커/이모티콘 제외)
- **대본**: Claude가 첫 장면 훅 → 핵심 내용 → 마무리 행동 유도 순으로 6~9개 장면 작성, 사진도 직접 보고 장면에 맞게 배치
- **음성**: Microsoft Edge 무료 한국어 TTS (API 키 필요 없음)
- **화면**: 상단 제목, 가운데 사진(천천히 확대되는 효과), 노란 핵심 자막, 하단 내레이션 자막
- **업로드용 제목·설명·해시태그**도 함께 생성 (`upload.txt`)

## 준비 (처음 한 번)

1. **Python 3.10 이상** 설치
2. **ffmpeg** 설치
   - Windows: `winget install ffmpeg`
   - Mac: `brew install ffmpeg`
3. 패키지 설치

   ```bash
   cd shorts-maker
   pip install -r requirements.txt
   ```

4. **Claude API 키** 발급: https://console.anthropic.com → API Keys
   - Mac/Linux: `export ANTHROPIC_API_KEY=sk-ant-...`
   - Windows(PowerShell): `$env:ANTHROPIC_API_KEY="sk-ant-..."`

## 사용법

```bash
python -m shorts_maker https://blog.naver.com/아이디/글번호
```

- 블로그 주소만 넣으면(`https://blog.naver.com/아이디`) **가장 최근 글**로 만듭니다.
- `m.blog.naver.com`, `PostView.naver?blogId=...&logNo=...`, `naver.me` 단축 주소도 됩니다.

결과는 `output/날짜_제목/` 폴더에 저장됩니다.

| 파일 | 내용 |
|---|---|
| `shorts.mp4` | 완성된 쇼츠 영상 |
| `upload.txt` | 업로드용 제목 / 설명 / 해시태그 |
| `script.json` | AI가 쓴 대본 (고쳐서 다시 만들 수 있음) |
| `images/` | 블로그에서 받은 사진 |

### 자주 쓰는 옵션

```bash
# 남성 목소리, 조금 더 빠르게
python -m shorts_maker <주소> --voice ko-KR-InJoonNeural --rate +20%

# 배경음악 넣기 (저작권 없는 음원 사용)
python -m shorts_maker <주소> --bgm music.mp3

# 대본 스타일 요청
python -m shorts_maker <주소> --prompt "손해사정 전문가가 설명하듯 신뢰감 있게, 40초 이내"
```

### 대본 고쳐서 다시 만들기

AI가 쓴 문장이 마음에 안 들면 `script.json`을 메모장으로 열어 `narration`(읽을 문장), `caption`(노란 자막),
`image_index`(사진 번호, -1이면 사진 없음)를 고친 뒤:

```bash
python -m shorts_maker --from-script output/폴더이름/script.json
```

AI를 다시 부르지 않으니 비용이 들지 않습니다.

## 비용

- Claude API: 글 1개당 대략 수십 원~100원대 (글 길이·사진 수에 따라 다름)
- TTS, ffmpeg: 무료

## 참고

- 비공개 글, 서로이웃 공개 글은 가져올 수 없습니다.
- 블로그 사진·글은 본인 소유 콘텐츠일 때 사용하세요.
- Edge TTS는 비공식 무료 서비스라 가끔 막힐 수 있습니다. 그럴 땐 잠시 후 다시 시도하세요.

## 폴더 구조

```
shorts_maker/
  naver.py     네이버 블로그 주소 해석, 글·사진 수집
  script.py    Claude로 쇼츠 대본 작성 (구조화 출력)
  tts.py       내레이션 음성 생성
  render.py    장면 그리기 + ffmpeg 영상 합성
  __main__.py  실행 진입점 (명령줄 옵션)
```
