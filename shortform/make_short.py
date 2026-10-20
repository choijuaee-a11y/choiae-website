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
import math
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
SCENE_PADDING = 0.45  # 장면마다 음성 뒤에 두는 여백(초)

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
# 3. 애니메이션 (Pillow로 프레임을 그려 FFmpeg로 바로 인코딩)
# ---------------------------------------------------------------------------

PAN_X, PAN_Y = 160, 260  # 배경이 천천히 움직일 여유 공간(px)


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def clamp(t):
    return max(0.0, min(1.0, t))


def ease_out(t):
    return 1 - (1 - clamp(t)) ** 3


def ease_out_back(t):
    """끝에서 살짝 튀어나왔다 돌아오는 탄성 효과."""
    t = clamp(t)
    return 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2


def blend(c1, c2, a):
    """c1 → c2 로 a(0~1) 만큼 섞은 색."""
    return tuple(int(c1[i] + (c2[i] - c1[i]) * a) for i in range(3))


def make_background(colors, width, height, seed=7):
    """세로 그라데이션 위에 흐릿한 금색 빛망울(보케)을 얹은 큰 배경."""
    import random
    from PIL import ImageFilter

    t, b = hex_rgb(colors["background"]), hex_rgb(colors["background_bottom"])
    col = Image.new("RGB", (1, height))
    for y in range(height):
        col.putpixel((0, y), blend(t, b, y / (height - 1)))
    bg = col.resize((width, height)).convert("RGBA")

    rnd = random.Random(seed)
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gold = hex_rgb(colors["highlight"])
    for _ in range(22):
        r = rnd.randint(30, 150)
        x, y = rnd.randint(0, width), rnd.randint(0, height)
        gd.ellipse([x - r, y - r, x + r, y + r], fill=(*gold, rnd.randint(18, 55)))
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    return Image.alpha_composite(bg, glow).convert("RGB")


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


def text_layer(text, font, color, highlight="", hl_color=None):
    """글자만 있는 투명 레이어. highlight 부분은 hl_color 로 칠하고 그 x 범위를 함께 돌려준다."""
    ascent, descent = font.getmetrics()
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    width = int(measure.textlength(text, font=font)) + 8
    layer = Image.new("RGBA", (width, ascent + descent + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    hl_range = None
    parts = re.split(f"({re.escape(highlight)})", text) if highlight else [text]
    x = 4
    for part in parts:
        if not part:
            continue
        is_hl = part == highlight
        d.text((x, 4), part, font=font, fill=(*(hl_color if is_hl else color), 255))
        w = d.textlength(part, font=font)
        if is_hl and hl_range is None:
            hl_range = (x, x + w)
        x += w
    return layer, hl_range


def paste_layer(frame, layer, cx, cy, scale=1.0, alpha=1.0):
    """레이어를 (cx, cy) 중심에 크기·투명도를 적용해 붙인다."""
    if alpha <= 0.01 or scale <= 0.01:
        return
    if abs(scale - 1.0) > 0.001:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))),
                             Image.BILINEAR)
    if alpha < 0.999:
        layer = layer.copy()
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    frame.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)), layer)


class SceneAnimation:
    """장면 하나의 레이아웃을 미리 계산해 두고, 시간 t 에 맞는 모습을 그린다."""

    def __init__(self, scene, idx, total, start, duration, speech, cfg, font_path):
        self.idx, self.total = idx, total
        self.start, self.duration, self.speech = start, duration, speech
        self.is_first, self.is_last = idx == 0, idx == total - 1
        self.colors = {k: hex_rgb(v) for k, v in cfg["colors"].items()}
        self.brand = cfg["brand"]
        c = self.colors
        measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))

        # 가운데 핵심 문구: 줄마다 레이어를 만들어 둔다
        caption = scene["caption"].strip()
        highlight = scene.get("highlight", "").strip()
        size = 104 if self.is_first else 88
        while True:
            font = ImageFont.truetype(font_path, size)
            lines = wrap_words(measure, caption, font, W - 160)
            if len(lines) <= 4 or size <= 56:
                break
            size -= 6
        line_h = int(size * 1.35)
        top = (H - line_h * len(lines)) / 2 - 80
        self.caption_lines = []
        for i, line in enumerate(lines):
            layer, hl = text_layer(line, font, c["text"], highlight, c["highlight"])
            self.caption_lines.append((layer, hl, top + line_h * i + line_h / 2))
        self.accent_y = top + line_h * len(lines) + 30

        # 내레이션 자막: 단어별 위치를 계산해 두고 말하는 속도에 맞춰 밝혀 준다
        self.narr_font = ImageFont.truetype(font_path, 44)
        self.words = []  # (단어, x, y, 이 단어가 끝나는 글자 비율)
        narr_lines = wrap_words(measure, scene["narration"].strip(), self.narr_font, W - 200)[:4]
        total_chars = sum(len(l.replace(" ", "")) for l in narr_lines) or 1
        seen, y = 0, self.accent_y + 70
        for line in narr_lines:
            x = (W - measure.textlength(line, font=self.narr_font)) / 2
            for word in line.split():
                seen += len(word)
                self.words.append((word, x, y, seen / total_chars))
                x += measure.textlength(word + " ", font=self.narr_font)
            y += 64

        self.small_font = ImageFont.truetype(font_path, 40)
        if self.is_last:
            btn_font = ImageFont.truetype(font_path, 64)
            tw = measure.textlength(self.brand["phone"], font=btn_font)
            self.button = Image.new("RGBA", (int(tw) + 120, 130), (0, 0, 0, 0))
            bd = ImageDraw.Draw(self.button)
            bd.rounded_rectangle([0, 0, self.button.width - 1, 129], radius=65, fill=(*c["highlight"], 255))
            bd.text((60, 22), self.brand["phone"], font=btn_font, fill=(*c["background"], 255))
            self.cta_layer, _ = text_layer(self.brand["cta"], self.small_font, c["sub_text"])

    def draw(self, frame, draw, t):
        c = self.colors
        bg = c["background_bottom"]
        # 장면이 끝날 때 글자들이 사라지는 정도 (마지막 장면은 끝까지 유지)
        exit_a = 1.0 if self.is_last else clamp((self.duration - t) / 0.25)

        # 1) 핵심 문구: 첫 장면은 '팡' 하고 튀어나오고, 나머지는 아래에서 미끄러져 올라온다
        for i, (layer, hl, cy) in enumerate(self.caption_lines):
            lt = (t - 0.09 * i) / 0.45
            if self.is_first:
                scale, dy = 0.55 + 0.45 * ease_out_back(lt), 0
            else:
                scale, dy = 1.0, (1 - ease_out(lt)) * 80
            paste_layer(frame, layer, W / 2, cy + dy, scale, clamp(lt * 2) * exit_a)

            # 강조 단어 아래 형광펜 밑줄이 왼쪽에서 오른쪽으로 그어진다
            if hl:
                p = ease_out((t - 0.09 * i - 0.45) / 0.35)
                if p > 0:
                    x0 = (W - layer.width) / 2 + hl[0]
                    x1 = x0 + (hl[1] - hl[0]) * p
                    yb = cy + layer.height / 2 - 4
                    draw.rectangle([x0, yb, x1, yb + 10], fill=blend(bg, c["highlight"], exit_a))

        # 2) 가운데 강조선이 양옆으로 늘어난다
        half = 60 * ease_out((t - 0.3) / 0.4)
        if half > 1:
            ay = self.accent_y
            draw.rectangle([W / 2 - half, ay, W / 2 + half, ay + 8], fill=blend(bg, c["highlight"], exit_a))

        # 3) 노래방 자막: 말한 단어는 밝게, 지금 말하는 단어는 금색, 아직 안 한 단어는 흐리게
        spoken = clamp((t - 0.1) / max(self.speech, 0.1))
        fade_in = ease_out(t / 0.3)
        prev_end = 0.0
        for word, x, y, end in self.words:
            if spoken >= end:
                color = c["sub_text"]
            elif spoken >= prev_end:
                color = c["highlight"]
            else:
                color = blend(bg, c["sub_text"], 0.35)
            prev_end = end
            draw.text((x, y), word, font=self.narr_font, fill=blend(bg, color, fade_in * exit_a))

        # 4) 하단: 마지막 장면은 상담 버튼이 튀어나와 두근거리고, 나머지는 전화번호 표시
        if self.is_last:
            bt = (t - 0.4) / 0.5
            if bt > 0:
                pulse = 1 + 0.04 * math.sin(2 * math.pi * max(t - 0.9, 0) / 1.1) if bt >= 1 else 1
                paste_layer(frame, self.button, W / 2, H - 405, ease_out_back(bt) * pulse)
                paste_layer(frame, self.cta_layer, W / 2, H - 270, alpha=ease_out((t - 0.7) / 0.4))
        else:
            text = f"상담 {self.brand['phone']}"
            tw = draw.textlength(text, font=self.small_font)
            draw.text(((W - tw) / 2, H - 300), text, font=self.small_font, fill=c["sub_text"])


def make_header(cfg, font_path, logo):
    """상단 로고 + 상호 + 태그라인 레이어."""
    c, brand = cfg["colors"], cfg["brand"]
    name_font = ImageFont.truetype(font_path, 52)
    tag_font = ImageFont.truetype(font_path, 26)
    layer = Image.new("RGBA", (W, 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    name_w = d.textlength(brand["name"], font=name_font)
    logo_w = logo.width + 24 if logo else 0
    x0 = (W - (logo_w + name_w)) / 2
    if logo:
        layer.paste(logo, (int(x0), 0), logo)
    d.text((x0 + logo_w, 10), brand["name"], font=name_font, fill=hex_rgb(c["text"]))
    tag_w = d.textlength(brand["tagline"], font=tag_font)
    d.text(((W - tag_w) / 2, 100), brand["tagline"], font=tag_font, fill=hex_rgb(c["highlight"]))
    return layer


def render_video(scenes, total, cfg, font_path, logo, audio, out_path, thumb_path):
    """모든 프레임을 그려 FFmpeg 로 바로 보내 MP4 를 만든다."""
    bg = make_background(cfg["colors"], W + PAN_X, H + PAN_Y)
    header = make_header(cfg, font_path, logo)
    gold = hex_rgb(cfg["colors"]["highlight"])

    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", str(audio),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", str(out_path)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    n_frames = int(round(total * FPS))
    thumb_frame = int(round(min(1.6, scenes[0].duration - 0.3) * FPS))
    current, last_pct = 0, -1
    try:
        for f in range(n_frames):
            t = f / FPS
            while current < len(scenes) - 1 and t >= scenes[current + 1].start:
                current += 1
            scene = scenes[current]

            # 배경은 영상 전체에 걸쳐 천천히 흘러간다
            ox = PAN_X / 2 * (1 + math.sin(2 * math.pi * t / 16))
            oy = PAN_Y * t / total
            frame = bg.crop((int(ox), int(oy), int(ox) + W, int(oy) + H))
            draw = ImageDraw.Draw(frame)

            # 상단 진행바 (부드럽게 채워짐) + 로고 (영상 시작 때 위에서 내려옴)
            draw.rectangle([0, 0, W, 10], fill=(60, 52, 44))
            draw.rectangle([0, 0, int(W * t / total), 10], fill=gold)
            ht = ease_out(t / 0.6)
            paste_layer(frame, header, W / 2, 140 + 75 - (1 - ht) * 120, alpha=ht)

            scene.draw(frame, draw, t - scene.start)

            if f == thumb_frame:
                frame.save(thumb_path)
            proc.stdin.write(frame.tobytes())

            pct = int(f / n_frames * 10)
            if pct != last_pct:
                print(f"    렌더링 {pct * 10}%", end="\r", flush=True)
                last_pct = pct
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode(errors="replace")
    if proc.wait() != 0:
        sys.exit(f"FFmpeg 오류:\n{err}")
    print("    렌더링 100%")


# ---------------------------------------------------------------------------
# 4. 오디오 (FFmpeg)
# ---------------------------------------------------------------------------

def run_ffmpeg(args):
    result = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"FFmpeg 오류:\n{result.stderr}")


def make_scene_audio(voice, duration, out_path):
    """장면 길이에 맞춘 음성 조각 (음성이 없으면 무음)."""
    audio_in = ["-i", str(voice)] if voice else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    run_ffmpeg([*audio_in, "-af", "apad", "-t", f"{duration:.3f}",
                "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(out_path)])


def concat_audio(parts, out_path, workdir):
    list_file = workdir / "audio.txt"
    list_file.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)])


def add_bgm(audio, bgm, volume, total, out_path):
    fade_st = max(total - 1.5, 0)
    run_ffmpeg([
        "-i", str(audio), "-stream_loop", "-1", "-i", str(bgm),
        "-filter_complex",
        f"[1:a]volume={volume},afade=t=out:st={fade_st:.2f}:d=1.5[bg];"
        f"[0:a][bg]amix=inputs=2:duration=first:normalize=0[a]",
        "-map", "[a]", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
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

    # 장면별 음성을 만들고 길이를 정한다
    scenes = script["scenes"]
    timeline, audio_parts, start = [], [], 0.0
    for i, scene in enumerate(scenes):
        print(f"  · 장면 {i + 1}/{len(scenes)}: {scene['caption']}")
        voice = None
        if use_voice:
            voice = work / f"voice_{i:02d}.mp3"
            try:
                make_voice(scene["narration"], voice, cfg)
                speech = media_duration(voice)
            except Exception as e:  # 네트워크 문제 등: 음성 없이 계속 진행
                print(f"    ! 음성 생성 실패 ({type(e).__name__}), 이 장면은 무음으로 만듭니다.")
                voice = None
        if voice is None:
            speech = max(2.2, len(scene["narration"]) * 0.11)
        duration = speech + SCENE_PADDING
        if i == len(scenes) - 1:
            duration += 1.2  # 마지막 상담 화면은 조금 더 보여준다

        part = work / f"audio_{i:02d}.wav"
        make_scene_audio(voice, duration, part)
        audio_parts.append(part)
        timeline.append(SceneAnimation(scene, i, len(scenes), start, duration, speech, cfg, font_path))
        start += duration
    total = start

    audio = work / "audio.wav"
    concat_audio(audio_parts, audio, work)
    if bgm_path and bgm_path.exists():
        mixed = work / "audio_bgm.wav"
        add_bgm(audio, bgm_path, cfg.get("bgm_volume", 0.12), total, mixed)
        audio = mixed

    print("  · 애니메이션 렌더링 중...")
    final = out_dir / "short.mp4"
    render_video(timeline, total, cfg, font_path, logo, audio, final, out_dir / "thumbnail.png")

    upload_text = "\n".join([
        f"[제목]\n{script['title']}",
        f"\n[설명]\n{script['description']}\n\n📞 상담 {cfg['brand']['phone']}",
        f"\n[해시태그]\n{' '.join(script['hashtags'])}",
    ])
    (out_dir / "upload.txt").write_text(upload_text + "\n", encoding="utf-8")
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
