"""장면 이미지·자막을 그리고 ffmpeg로 세로 영상(1080x1920)을 만든다."""
from __future__ import annotations

import glob
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H = 1080, 1920
FPS = 30
PHOTO_W = 1000          # 가운데 사진 폭
PHOTO_CENTER_Y = 880    # 가운데 사진 세로 중심
PHOTO_MAX_H = 1050

FONT_CANDIDATES = [
    # Windows
    "C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/malgun.ttf",
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc", "/Library/Fonts/NanumGothicBold.ttf",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def find_font(user_font: str | None = None) -> str:
    if user_font:
        return user_font
    for c in FONT_CANDIDATES:
        if Path(c).exists():
            return c
    for pattern in ("/usr/share/fonts/**/*CJK*Bold*", "/usr/share/fonts/**/*Nanum*", "/usr/share/fonts/**/*CJK*"):
        hits = glob.glob(pattern, recursive=True)
        if hits:
            return hits[0]
    raise FileNotFoundError(
        "한글 폰트를 찾지 못했어요. --font 옵션으로 .ttf/.otf/.ttc 파일 경로를 지정해 주세요."
    )


def check_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        hint = {
            "Windows": "winget install ffmpeg",
            "Darwin": "brew install ffmpeg",
        }.get(platform.system(), "sudo apt install ffmpeg")
        raise RuntimeError(f"ffmpeg가 필요해요. 설치: {hint}")


# ---------- 그리기 도우미 ----------

def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """픽셀 폭 기준 줄바꿈. 공백 우선, 너무 긴 단어는 글자 단위로 자른다."""
    lines: list[str] = []
    cur = ""
    for word in text.split(" "):
        cand = f"{cur} {word}".strip()
        if font.getlength(cand) <= max_w:
            cur = cand
            continue
        if cur:
            lines.append(cur)
        cur = ""
        for ch in word:
            if font.getlength(cur + ch) > max_w and cur:
                lines.append(cur)
                cur = ""
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def _draw_text_block(draw: ImageDraw.ImageDraw, text: str, font, center_y: int, max_w: int,
                     fill, stroke=0, stroke_fill="black", box=None, line_gap=14) -> None:
    lines = _wrap(text, font, max_w)
    asc, desc = font.getmetrics()
    lh = asc + desc + line_gap
    total = lh * len(lines) - line_gap
    y = center_y - total // 2
    if box:
        widest = max(font.getlength(l) for l in lines)
        pad_x, pad_y = 36, 24
        draw.rounded_rectangle(
            [W / 2 - widest / 2 - pad_x, y - pad_y, W / 2 + widest / 2 + pad_x, y + total + pad_y],
            radius=28, fill=box,
        )
    for line in lines:
        draw.text((W / 2, y), line, font=font, fill=fill, anchor="ma",
                  stroke_width=stroke, stroke_fill=stroke_fill)
        y += lh


def _gradient(seed: int) -> Image.Image:
    palettes = [((32, 46, 88), (14, 18, 32)), ((70, 28, 64), (20, 12, 30)), ((20, 70, 72), (8, 22, 26))]
    top, bottom = palettes[seed % len(palettes)]
    g = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        g.putpixel((0, y), tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    return g.resize((W, H))


def render_background(photo: Path | None, out: Path, seed: int = 0) -> None:
    if photo is None:
        _gradient(seed).save(out)
        return
    img = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
    bg = ImageOps.fit(img, (W, H)).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.55)
    bg.save(out)


def render_photo(photo: Path, out: Path) -> None:
    """가운데에 놓일 둥근 모서리 사진 (투명 배경 PNG)."""
    img = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
    img = ImageOps.contain(img, (PHOTO_W, PHOTO_MAX_H))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *img.size], radius=36, fill=255)
    rgba = img.convert("RGBA")
    rgba.putalpha(mask)
    rgba.save(out)


def render_overlay(title: str, caption: str, font_path: str, out: Path, has_photo: bool) -> None:
    """제목(상단)과 핵심 자막(사진 아래)을 투명 PNG로."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    _draw_text_block(d, title, ImageFont.truetype(font_path, 64), 190, 920,
                     fill="white", box=(0, 0, 0, 170))
    cap_y = 1500 if has_photo else 900
    _draw_text_block(d, caption, ImageFont.truetype(font_path, 88), cap_y, 960,
                     fill=(255, 221, 51), stroke=6)
    layer.save(out)


def render_subtitle(text: str, font_path: str, out: Path) -> None:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_text_block(ImageDraw.Draw(layer), text, ImageFont.truetype(font_path, 60), 1700, 940,
                     fill="white", stroke=5)
    layer.save(out)


def split_subtitles(narration: str, max_chars: int = 18) -> list[str]:
    """내레이션을 화면에 한 번에 보일 짧은 덩어리로 나눈다."""
    chunks, cur = [], ""
    for word in narration.split():
        if cur and len(cur) + 1 + len(word) > max_chars:
            chunks.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
        if cur.endswith((".", "?", "!", ",")) and len(cur) >= max_chars * 0.5:
            chunks.append(cur)
            cur = ""
    if cur:
        chunks.append(cur)
    return chunks or [narration]


# ---------- 영상 합성 ----------

@dataclass
class SceneAssets:
    background: Path
    photo: Path | None
    overlay: Path
    subtitles: list[Path]
    sub_times: list[tuple[float, float]]
    audio: Path
    duration: float


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg 실패:\n" + proc.stderr[-2000:])


def render_scene_video(a: SceneAssets, out: Path) -> None:
    inputs = ["-loop", "1", "-framerate", str(FPS), "-i", str(a.background)]
    idx = 1
    filters = ["[0:v]scale=1080:1920,setsar=1[bg]"]
    last = "bg"
    if a.photo:
        inputs += ["-loop", "1", "-framerate", str(FPS), "-i", str(a.photo)]
        d = max(a.duration, 0.1)
        # 사진이 천천히 커지는 켄번스 효과
        filters.append(
            f"[{idx}:v]scale=w='trunc(iw*(1+0.06*t/{d:.3f})/2)*2':h=-2:eval=frame[ph]"
        )
        filters.append(f"[{last}][ph]overlay=x='(W-w)/2':y='{PHOTO_CENTER_Y}-h/2'[v{idx}]")
        last = f"v{idx}"
        idx += 1
    inputs += ["-loop", "1", "-framerate", str(FPS), "-i", str(a.overlay)]
    filters.append(f"[{last}][{idx}:v]overlay=0:0[v{idx}]")
    last = f"v{idx}"
    idx += 1
    for sub, (s, e) in zip(a.subtitles, a.sub_times):
        inputs += ["-loop", "1", "-framerate", str(FPS), "-i", str(sub)]
        filters.append(f"[{last}][{idx}:v]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})'[v{idx}]")
        last = f"v{idx}"
        idx += 1
    inputs += ["-i", str(a.audio)]
    audio_idx = idx

    _run([
        "ffmpeg", "-y", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(filters),
        "-map", f"[{last}]", "-map", f"{audio_idx}:a",
        "-af", "apad", "-t", f"{a.duration:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
        str(out),
    ])


def concat_videos(parts: list[Path], out: Path, bgm: Path | None = None, bgm_volume: float = 0.12) -> None:
    listfile = out.parent / "concat.txt"
    listfile.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    joined = out if bgm is None else out.parent / "_joined.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listfile),
          "-c", "copy", "-movflags", "+faststart", str(joined)])
    if bgm is not None:
        _run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(joined), "-stream_loop", "-1", "-i", str(bgm),
            "-filter_complex",
            f"[1:a]volume={bgm_volume}[b];[0:a][b]amix=inputs=2:duration=first:dropout_transition=0[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", str(out),
        ])
        joined.unlink(missing_ok=True)
