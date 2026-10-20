# 숏폼 자동 생성기

주제 한 줄만 입력하면 유튜브 쇼츠·인스타 릴스·틱톡용 세로(1080×1920) 영상을 자동으로 만듭니다.

```
주제 입력 → AI 대본(Claude) → 음성 내레이션(무료 TTS) → 자막 화면 → MP4 완성
```

결과 폴더에는 아래 파일이 생깁니다.

| 파일 | 내용 |
|---|---|
| `short.mp4` | 완성된 세로 영상 (30~45초) |
| `upload.txt` | 업로드할 때 붙여넣을 제목·설명·해시태그 |
| `thumbnail.png` | 첫 장면 이미지 (썸네일용) |
| `script.json` | 대본. 고친 뒤 `--script` 로 다시 만들 수 있음 |

영상에 들어가는 애니메이션

- 첫 장면 문구가 '팡' 하고 튀어나오고, 이후 장면 문구는 아래에서 미끄러져 올라옵니다
- 강조 단어 아래로 금색 형광펜 밑줄이 그어집니다
- 아래 자막은 노래방처럼 말하는 속도에 맞춰 단어가 금색 → 흰색으로 밝아집니다
- 배경의 금색 빛망울이 영상 내내 천천히 흘러갑니다
- 상단 진행바가 부드럽게 차오르고, 마지막 장면의 상담 전화 버튼은 두근거리듯 커졌다 작아집니다

## 1. 처음 한 번만 설치

1. **Python 3.10 이상**: https://www.python.org/downloads/ (설치할 때 "Add Python to PATH" 체크)
2. **FFmpeg** (영상 합성 도구)
   - Windows: 명령 프롬프트에서 `winget install Gyan.FFmpeg`
   - Mac: `brew install ffmpeg`
3. 이 폴더(`shortform`)에서 필요한 패키지 설치
   ```bash
   pip install -r requirements.txt
   ```
4. **Claude API 키** 발급: https://console.anthropic.com → API Keys
   - Windows: `setx ANTHROPIC_API_KEY "발급받은키"` 입력 후 명령 프롬프트를 새로 열기
   - Mac: `export ANTHROPIC_API_KEY="발급받은키"` (`~/.zshrc` 에 넣어두면 계속 유지)

> API 키 없이도 대본 파일(`--script`)로 영상은 만들 수 있습니다.

## 2. 사용법

```bash
# 주제 하나로 영상 만들기
python make_short.py "암 진단비 거절당했을 때 확인할 3가지"

# topics.txt 에 적어둔 주제를 한 번에 여러 편 만들기
python make_short.py --topics topics.txt

# AI 없이 대본 파일로 만들기 (예시 대본 포함)
python make_short.py --script examples/sample_script.json

# AI가 만든 대본을 손본 뒤 다시 만들기
python make_short.py --script output/20261020_..._제목/script.json
```

옵션

| 옵션 | 설명 |
|---|---|
| `--no-voice` | 음성 없이 자막 영상만 |
| `--bgm 파일.mp3` | 배경음악 지정 (기본: `assets/bgm.mp3` 가 있으면 자동 사용) |
| `--out 폴더` | 결과 저장 위치 (기본: `output/`) |

## 3. 꾸미기 (`config.json`)

| 항목 | 설명 |
|---|---|
| `brand` | 상호, 전화번호, 마지막 장면 문구, 로고 경로 |
| `colors` | 배경·글자·강조(금색) 색상 |
| `font` | 비워두면 맑은 고딕(Windows)/애플 SD 고딕(Mac)을 자동 사용. 다른 폰트를 쓰려면 `.ttf` 경로 입력 |
| `voice.name` | 목소리. `ko-KR-SunHiNeural`(여성), `ko-KR-InJoonNeural`(남성), `ko-KR-HyunsuNeural`(남성) |
| `voice.rate` | 말 빠르기. `+10%`, `+20%`, `-5%` 등 |
| `claude.model` | 대본을 쓸 Claude 모델 |
| `bgm`, `bgm_volume` | 배경음악 파일과 볼륨 (0.1 정도 권장) |

배경음악은 저작권 걱정 없는 곡을 쓰세요. 유튜브 스튜디오 → 오디오 보관함에서 무료 곡을 받아
`assets/bgm.mp3` 로 저장해 두면 모든 영상에 자동으로 들어갑니다.

## 4. 참고

- 대본 생성은 Claude API를 사용하므로 사용량만큼 요금이 나옵니다 (영상 1편당 대략 수십 원 수준).
  거절된 요청은 자동으로 다른 모델로 다시 시도하도록 설정되어 있습니다.
- 음성은 Microsoft Edge의 무료 TTS(`edge-tts`)를 사용하며 인터넷 연결이 필요합니다.
  음성 생성에 실패한 장면은 무음으로 만들어지니, 그럴 때는 잠시 후 다시 실행하세요.
- AI 대본에는 "무조건 받아드립니다" 같은 결과 보장·과장 표현과 업무 범위를 넘는 표현을 쓰지 않도록
  지시해 두었습니다. 그래도 **업로드 전에 내용을 꼭 한 번 확인**해 주세요.
