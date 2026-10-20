"""최애손해사정 숏폼 자동 생성기

주제 한 줄 → AI 대본 → 음성(TTS) → 자막 화면 → 세로(9:16) MP4 완성.

사용 예:
    python make_short.py "암 진단비 거절당했을 때 확인할 3가지"
    python make_short.py --topics topics.txt          # 여러 주제 한 번에
    python make_short.py --script examples/sample_script.json   # API 키 없이 대본 파일로
"""

import argparse
import asyncio
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
W, H = 1080, 1920
FPS = 30
SCENE_PADDING = 0.35  # 장면마다 음성 뒤에 두는 여백(초)

# 운영체제별로 흔히 설치된 한글 굵은 폰트 후보
FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
]


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------

def load_config():
    with open(BASE_DIR / "config.json", encoding="utf-8") as f:
        return json.load(f)


def resolve(path):
    """config.json 기준 상대경로를 절대경로로 바꾼다."""
    p = Path(path)
    return p if p.is_absolute() else (BASE_DIR / p).resolve()


def find_font(cfg):
    if cfg.get("font"):
        return str(resolve(cfg["font"]))
    for cand in FONT_CANDIDATES:
        if Path(cand).exists():
            return cand
    sys.exit("한글 폰트를 찾지 못했습니다. config.json 의 \"font\" 에 .ttf 경로를 넣어 주세요.")


# ---------------------------------------------------------------------------
# 1. 대본 생성 (Claude)
# ---------------------------------------------------------------------------

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "업로드용 제목 (40자 이내, 호기심 유발)"},
        "scenes": {
            "type": "array",
            "description": "6~9개 장면. 첫 장면은 3초 안에 시선을 잡는 후킹, 마지막 장면은 상담 안내.",
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string", "description": "성우가 읽을 문장 (1~2문장, 구어체)"},
                    "caption": {"type": "string", "description": "화면에 크게 띄울 핵심 문구 (25자 이내, 이모지·특수기호 사용 금지)"},
                    "highlight": {"type": "string", "description": "caption 안에서 금색으로 강조할 단어 (caption에 그대로 포함된 단어, 없으면 빈 문자열)"},
                },
                "required": ["narration", "caption", "highlight"],
                "additionalProperties": False,
            },
        },
        "description": {"type": "string", "description": "업로드용 설명글 (3~5줄)"},
        "hashtags": {"type": "array", "items": {"type": "string"}, "description": "해시태그 8~12개, # 포함"},
    },
    "required": ["title", "scenes", "description", "hashtags"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """당신은 손해사정 사무소의 유튜브 쇼츠·인스타 릴스 대본 작가입니다.

[사무소 정보]
- 상호: {name} ({tagline})
- 대표손해사정사 최주애 (신체손해사정사·차량손해사정사 자격)
- 주요 분야: 암 진단비, 심·뇌혈관질환, 사망·후유장해, 고지·통지의무 위반 분쟁, 교통사고·배상책임
- 슬로건: "아파본 사람이 압니다. 제대로 보상받는 일이 얼마나 중요한지."
- 상담: 전화 {phone}, 카카오톡 채널, 홈페이지 상담 신청 (방문 상담은 예약제)

[대본 원칙]
- 길이: 낭독 기준 30~45초. 짧고 리듬감 있는 구어체 문장.
- 첫 장면은 시청자가 스크롤을 멈추게 하는 질문이나 반전으로 시작.
- 실제로 도움이 되는 정보(확인할 서류, 약관 용어, 흔한 거절 사유 등)를 구체적으로 담기.
- 마지막 장면은 부담 없는 상담 권유로 마무리.

[반드시 지킬 광고·법규 기준]
- "무조건", "100% 받아드림", "최대 보상 보장" 등 결과를 보장하거나 과장하는 표현 금지.
- 보험회사나 특정인을 비방하지 않기.
- 소송·법률 대리처럼 손해사정사 업무 범위를 넘는 서비스를 암시하지 않기.
- 사실이 불확실한 수치나 판례는 쓰지 않기. 일반적인 안내임을 전제로 설명.
"""


def generate_script(topic, cfg):
    try:
        import anthropic
    except ImportError:
        sys.exit("anthropic 패키지가 없습니다: pip install -r requirements.txt")

    brand = cfg["brand"]
    client = anthropic.Anthropic()
    print(f"  · 대본 생성 중 ({cfg['claude']['model']})...")
    try:
        response = client.beta.messages.create(
            model=cfg["claude"]["model"],
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={
                "effort": cfg["claude"].get("effort", "medium"),
                "format": {"type": "json_schema", "schema": SCRIPT_SCHEMA},
            },
            system=SYSTEM_PROMPT.format(**brand),
            messages=[{"role": "user", "content": f"주제: {topic}\n\n이 주제로 숏폼 대본을 써 주세요."}],
        )
    except anthropic.AuthenticationError:
        sys.exit("API 키가 올바르지 않습니다. ANTHROPIC_API_KEY 환경변수를 확인해 주세요.")
    except anthropic.RateLimitError:
        sys.exit("API 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.")
    except anthropic.APIStatusError as e:
        sys.exit(f"Claude API 오류 ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Claude API에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요.")

    if response.stop_reason == "refusal":
        sys.exit("이 주제로는 대본을 만들 수 없다는 응답을 받았습니다. 주제를 바꿔 주세요.")
    if response.stop_reason == "max_tokens":
        sys.exit("대본이 너무 길어 중간에 잘렸습니다. 다시 시도해 주세요.")

    text = "".join(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def load_script(path):
    with open(path, encoding="utf-8") as f:
        script = json.load(f)
    for key in ("title", "scenes"):
        if key not in script:
            sys.exit(f"대본 파일에 '{key}' 항목이 없습니다: {path}")
    script.setdefault("description", "")
    script.setdefault("hashtags", [])
    for s in script["scenes"]:
        s.setdefault("caption", s["narration"])
        s.setdefault("highlight", "")
    return script


# ---------------------------------------------------------------------------
# 2. 음성 (edge-tts, 무료)
# ---------------------------------------------------------------------------

async def _tts(text, out_path, voice, rate):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out_path))


def make_voice(text, out_path, cfg):
    asyncio.run(_tts(text, out_path, cfg["voice"]["name"], cfg["voice"]["rate"]))


def media_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


# ---------------------------------------------------------------------------
# 3. 장면 이미지 (Pillow)
# ---------------------------------------------------------------------------

def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def gradient_background(top, bottom):
    t, b = hex_rgb(top), hex_rgb(bottom)
    col = Image.new("RGB", (1, H))
    for y in range(H):
        r = y / (H - 1)
        col.putpixel((0, y), tuple(int(t[i] + (b[i] - t[i]) * r) for i in range(3)))
    return col.resize((W, H))


def wrap_words(draw, text, font, max_width):
    """단어 단위로 줄바꿈. 한 단어가 너무 길면 글자 단위로 자른다."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            line = trial
            continue
        if line:
            lines.append(line)
        line = word
        while draw.textlength(line, font=font) > max_width:
            cut = len(line)
            while cut > 1 and draw.textlength(line[:cut], font=font) > max_width:
                cut -= 1
            lines.append(line[:cut])
            line = line[cut:]
    if line:
        lines.append(line)
    return lines


def draw_highlighted_line(draw, x, y, line, highlight, font, color, hl_color):
    """line 안의 highlight 부분만 금색으로 그린다."""
    parts = re.split(f"({re.escape(highlight)})", line) if highlight else [line]
    for part in parts:
        if not part:
            continue
        draw.text((x, y), part, font=font, fill=hl_color if part == highlight else color)
        x += draw.textlength(part, font=font)


def render_scene(scene, idx, total, cfg, font_path, logo, out_path):
    colors = cfg["colors"]
    brand = cfg["brand"]
    img = gradient_background(colors["background"], colors["background_bottom"])
    draw = ImageDraw.Draw(img)

    # 상단 진행바
    bar_w = int(W * (idx + 1) / total)
    draw.rectangle([0, 0, W, 10], fill=(60, 52, 44))
    draw.rectangle([0, 0, bar_w, 10], fill=hex_rgb(colors["highlight"]))

    # 상단 로고 + 상호
    top = 150
    name_font = ImageFont.truetype(font_path, 52)
    tag_font = ImageFont.truetype(font_path, 26)
    name_w = draw.textlength(brand["name"], font=name_font)
    logo_w = logo.width + 24 if logo else 0
    x0 = (W - (logo_w + name_w)) / 2
    if logo:
        img.paste(logo, (int(x0), top - 10), logo)
    draw.text((x0 + logo_w, top), brand["name"], font=name_font, fill=hex_rgb(colors["text"]))
    tag_w = draw.textlength(brand["tagline"], font=tag_font)
    draw.text(((W - tag_w) / 2, top + 90), brand["tagline"], font=tag_font, fill=hex_rgb(colors["highlight"]))

    # 가운데 핵심 문구 (첫 장면은 더 크게)
    caption = scene["caption"].strip()
    size = 104 if idx == 0 else 88
    while True:
        font = ImageFont.truetype(font_path, size)
        lines = wrap_words(draw, caption, font, W - 160)
        if len(lines) <= 4 or size <= 56:
            break
        size -= 6
    line_h = int(size * 1.35)
    block_h = line_h * len(lines)
    y = (H - block_h) / 2 - 40
    highlight = scene.get("highlight", "").strip()
    for line in lines:
        lw = draw.textlength(line, font=font)
        draw_highlighted_line(draw, (W - lw) / 2, y, line, highlight, font,
                              hex_rgb(colors["text"]), hex_rgb(colors["highlight"]))
        y += line_h

    # 강조선
    accent_y = y + 30
    draw.rectangle([W / 2 - 60, accent_y, W / 2 + 60, accent_y + 8], fill=hex_rgb(colors["highlight"]))

    # 강조선 아래 내레이션 자막
    narr_font = ImageFont.truetype(font_path, 44)
    ny = accent_y + 70
    for line in wrap_words(draw, scene["narration"].strip(), narr_font, W - 200)[:4]:
        lw = draw.textlength(line, font=narr_font)
        draw.text(((W - lw) / 2, ny), line, font=narr_font, fill=hex_rgb(colors["sub_text"]))
        ny += 64

    # 하단 안내 (마지막 장면은 큰 상담 버튼)
    sub_font = ImageFont.truetype(font_path, 40)
    if idx == total - 1:
        btn_font = ImageFont.truetype(font_path, 64)
        text = brand["phone"]
        tw = draw.textlength(text, font=btn_font)
        bx0, by0 = (W - tw) / 2 - 60, H - 470
        draw.rounded_rectangle([bx0, by0, bx0 + tw + 120, by0 + 130], radius=65,
                               fill=hex_rgb(colors["highlight"]))
        draw.text(((W - tw) / 2, by0 + 22), text, font=btn_font, fill=hex_rgb(colors["background"]))
        cta_w = draw.textlength(brand["cta"], font=sub_font)
        draw.text(((W - cta_w) / 2, by0 + 175), brand["cta"], font=sub_font, fill=hex_rgb(colors["sub_text"]))
    else:
        text = f"상담 {brand['phone']}"
        tw = draw.textlength(text, font=sub_font)
        draw.text(((W - tw) / 2, H - 300), text, font=sub_font, fill=hex_rgb(colors["sub_text"]))

    img.save(out_path)


# ---------------------------------------------------------------------------
# 4. 영상 합성 (FFmpeg)
# ---------------------------------------------------------------------------

def run_ffmpeg(args):
    result = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"FFmpeg 오류:\n{result.stderr}")


def make_clip(image, voice, duration, out_path):
    fade_out = max(duration - 0.15, 0)
    video_filter = f"fade=t=in:st=0:d=0.15,fade=t=out:st={fade_out:.2f}:d=0.15,format=yuv420p"
    audio_in = ["-i", str(voice)] if voice else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    run_ffmpeg([
        "-loop", "1", "-framerate", str(FPS), "-i", str(image), *audio_in,
        "-t", f"{duration:.2f}", "-vf", video_filter, "-af", "apad",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(FPS),
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k",
        str(out_path),
    ])


def concat_clips(clips, out_path, workdir):
    list_file = workdir / "clips.txt"
    list_file.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)])


def add_bgm(video, bgm, volume, out_path):
    total = media_duration(video)
    fade_st = max(total - 1.5, 0)
    run_ffmpeg([
        "-i", str(video), "-stream_loop", "-1", "-i", str(bgm),
        "-filter_complex",
        f"[1:a]volume={volume},afade=t=out:st={fade_st:.2f}:d=1.5[bg];"
        f"[0:a][bg]amix=inputs=2:duration=first:normalize=0[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        "-t", f"{total:.2f}", str(out_path),
    ])


# ---------------------------------------------------------------------------
# 전체 파이프라인
# ---------------------------------------------------------------------------

def slugify(text, max_len=30):
    text = re.sub(r"[^\w가-힣]+", "_", text).strip("_")
    return text[:max_len] or "short"


def build_short(script, cfg, out_root, use_voice=True, bgm_path=None):
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = out_root / f"{stamp}_{slugify(script['title'])}"
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    (out_dir / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

    font_path = find_font(cfg)
    logo = None
    logo_path = resolve(cfg["brand"].get("logo", ""))
    if cfg["brand"].get("logo") and logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((84, 84))

    scenes = script["scenes"]
    clips = []
    for i, scene in enumerate(scenes):
        print(f"  · 장면 {i + 1}/{len(scenes)}: {scene['caption']}")
        image = work / f"scene_{i:02d}.png"
        render_scene(scene, i, len(scenes), cfg, font_path, logo, image)

        voice = None
        if use_voice:
            voice = work / f"voice_{i:02d}.mp3"
            try:
                make_voice(scene["narration"], voice, cfg)
                duration = media_duration(voice) + SCENE_PADDING
            except Exception as e:  # 네트워크 문제 등: 음성 없이 계속 진행
                print(f"    ! 음성 생성 실패 ({type(e).__name__}), 이 장면은 무음으로 만듭니다.")
                voice = None
        if voice is None:
            duration = max(2.5, len(scene["narration"]) * 0.12)

        clip = work / f"clip_{i:02d}.mp4"
        make_clip(image, voice, duration, clip)
        clips.append(clip)

    final = out_dir / "short.mp4"
    if bgm_path and bgm_path.exists():
        merged = work / "merged.mp4"
        concat_clips(clips, merged, work)
        add_bgm(merged, bgm_path, cfg.get("bgm_volume", 0.12), final)
    else:
        concat_clips(clips, final, work)

    upload_text = "\n".join([
        f"[제목]\n{script['title']}",
        f"\n[설명]\n{script['description']}\n\n📞 상담 {cfg['brand']['phone']}",
        f"\n[해시태그]\n{' '.join(script['hashtags'])}",
    ])
    (out_dir / "upload.txt").write_text(upload_text + "\n", encoding="utf-8")
    shutil.copy(work / "scene_00.png", out_dir / "thumbnail.png")
    return out_dir, media_duration(final)


def main():
    parser = argparse.ArgumentParser(description="최애손해사정 숏폼 자동 생성기")
    parser.add_argument("topic", nargs="?", help="영상 주제 (예: \"실손보험 청구 꿀팁\")")
    parser.add_argument("--topics", help="주제 목록 파일 (한 줄에 하나, #으로 시작하면 무시)")
    parser.add_argument("--script", help="AI 대신 사용할 대본 JSON 파일")
    parser.add_argument("--no-voice", action="store_true", help="음성 없이 자막 영상만 생성")
    parser.add_argument("--bgm", help="배경음악 파일 (기본: config.json 의 bgm)")
    parser.add_argument("--out", default=str(BASE_DIR / "output"), help="결과 저장 폴더")
    args = parser.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} 이 설치되어 있지 않습니다. README 의 설치 방법을 확인해 주세요.")

    cfg = load_config()
    bgm = Path(args.bgm) if args.bgm else (resolve(cfg["bgm"]) if cfg.get("bgm") else None)
    out_root = Path(args.out)

    jobs = []  # (설명, 대본을 만드는 함수)
    if args.script:
        jobs.append((args.script, lambda: load_script(args.script)))
    elif args.topics:
        with open(args.topics, encoding="utf-8") as f:
            topics = [t.strip() for t in f if t.strip() and not t.startswith("#")]
        jobs += [(t, lambda t=t: generate_script(t, cfg)) for t in topics]
    elif args.topic:
        jobs.append((args.topic, lambda: generate_script(args.topic, cfg)))
    else:
        parser.print_help()
        return

    for n, (label, get_script) in enumerate(jobs, 1):
        print(f"\n[{n}/{len(jobs)}] {label}")
        script = get_script()
        out_dir, seconds = build_short(script, cfg, out_root, use_voice=not args.no_voice, bgm_path=bgm)
        print(f"  ✔ 완성 ({seconds:.1f}초): {out_dir / 'short.mp4'}")


if __name__ == "__main__":
    main()
