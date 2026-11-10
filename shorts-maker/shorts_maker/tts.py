"""내레이션 음성 만들기 (Microsoft Edge 무료 TTS 사용)."""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

DEFAULT_VOICE = "ko-KR-SunHiNeural"  # 여성. 남성: ko-KR-InJoonNeural, ko-KR-HyunsuMultilingualNeural


def audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


async def _edge_tts(text: str, out: Path, voice: str, rate: str) -> None:
    import edge_tts

    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def _silent(text: str, out: Path) -> None:
    """테스트용: 네트워크 없이 글자 수에 비례한 무음 오디오를 만든다."""
    seconds = max(1.5, len(text) * 0.12)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", f"{seconds:.2f}", "-q:a", "9", str(out)],
        check=True,
    )


def synthesize(texts: list[str], out_dir: Path, voice: str = DEFAULT_VOICE,
               rate: str = "+10%", engine: str = "edge") -> list[tuple[Path, float]]:
    """각 문장을 mp3로 만들고 (경로, 길이초) 목록을 돌려준다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for i, text in enumerate(texts):
        out = out_dir / f"voice_{i:02d}.mp3"
        if engine == "silent":
            _silent(text, out)
        else:
            asyncio.run(_edge_tts(text, out, voice, rate))
        results.append((out, audio_duration(out)))
    return results
