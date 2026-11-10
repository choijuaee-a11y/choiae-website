"""사용법: python -m shorts_maker <네이버 블로그 주소> [옵션]"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from . import naver, render, tts
from .script import ShortsScript, write_script


def build_video(script: ShortsScript, images: list[Path], out_dir: Path, *, font: str,
                voice: str, rate: str, engine: str, bgm: Path | None) -> Path:
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    print("2) 내레이션 음성 생성 중...")
    voices = tts.synthesize([s.narration for s in script.scenes], work, voice=voice, rate=rate, engine=engine)

    print("3) 장면 그리는 중...")
    parts: list[Path] = []
    for i, (scene, (audio, dur)) in enumerate(zip(script.scenes, voices)):
        photo_src = images[scene.image_index] if scene.image_index >= 0 else None
        bg = work / f"bg_{i:02d}.png"
        render.render_background(photo_src, bg, seed=i)
        photo = None
        if photo_src:
            photo = work / f"photo_{i:02d}.png"
            render.render_photo(photo_src, photo)
        overlay = work / f"overlay_{i:02d}.png"
        render.render_overlay(script.title, scene.caption, font, overlay, has_photo=photo is not None)

        chunks = render.split_subtitles(scene.narration)
        total_chars = sum(len(c) for c in chunks)
        subs, times, t = [], [], 0.0
        for j, chunk in enumerate(chunks):
            p = work / f"sub_{i:02d}_{j:02d}.png"
            render.render_subtitle(chunk, font, p)
            span = dur * len(chunk) / total_chars
            subs.append(p)
            times.append((t, t + span))
            t += span

        scene_dur = dur + 0.3  # 장면 사이 짧은 숨 고르기
        part = work / f"scene_{i:02d}.mp4"
        render.render_scene_video(
            render.SceneAssets(bg, photo, overlay, subs, times, audio, scene_dur), part
        )
        parts.append(part)
        print(f"   장면 {i + 1}/{len(script.scenes)} 완료 ({scene_dur:.1f}초)")

    print("4) 영상 합치는 중...")
    final = out_dir / "shorts.mp4"
    render.concat_videos(parts, final, bgm=bgm)
    return final


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="shorts_maker", description="네이버 블로그 글 → 쇼츠 영상")
    ap.add_argument("url", nargs="?", help="네이버 블로그 글 주소 (블로그 주소만 주면 최신 글)")
    ap.add_argument("-o", "--out", default="output", help="결과 폴더 (기본: output)")
    ap.add_argument("--voice", default=tts.DEFAULT_VOICE, help="TTS 목소리 (예: ko-KR-InJoonNeural)")
    ap.add_argument("--rate", default="+10%", help="말하기 속도 (예: +0%%, +20%%)")
    ap.add_argument("--bgm", type=Path, help="배경음악 mp3 파일 (선택)")
    ap.add_argument("--font", help="한글 폰트 파일 경로 (자동 탐색 실패 시)")
    ap.add_argument("--prompt", default="", help="대본에 대한 추가 요청 (예: '20대 말투로', '40초 이내')")
    ap.add_argument("--from-script", type=Path,
                    help="이전에 만든 script.json을 고쳐서 AI 호출 없이 영상만 다시 만들기")
    ap.add_argument("--html", type=Path, help="(테스트용) 저장해 둔 블로그 HTML 파일 사용")
    ap.add_argument("--tts", choices=["edge", "silent"], default="edge", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    render.check_ffmpeg()
    font = render.find_font(args.font)

    if args.from_script:
        out_dir = args.from_script.parent
        script = ShortsScript.model_validate_json(args.from_script.read_text(encoding="utf-8"))
        images = sorted((out_dir / "images").glob("img_*"))
        print("1) 저장된 대본 사용:", args.from_script)
    else:
        if not args.url and not args.html:
            ap.error("블로그 주소를 입력해 주세요.")
        print("1) 블로그 글 가져오는 중...")
        if args.html:
            post = naver.parse_post_html(args.html.read_text(encoding="utf-8"), url=str(args.html))
        else:
            post = naver.fetch_post(args.url)
        print(f"   제목: {post.title}  (문단 {len(post.paragraphs)}개, 이미지 {len(post.image_urls)}개)")

        slug = re.sub(r"[^\w가-힣]+", "_", post.title)[:30].strip("_") or "post"
        out_dir = Path(args.out) / f"{time.strftime('%Y%m%d_%H%M%S')}_{slug}"
        images = naver.download_images(post.image_urls, out_dir / "images")

        print("   Claude가 쇼츠 대본을 쓰는 중...")
        script = write_script(post, images, args.prompt)
        (out_dir / "script.json").write_text(
            json.dumps(script.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    final = build_video(script, images, out_dir, font=font, voice=args.voice, rate=args.rate,
                        engine=args.tts, bgm=args.bgm)

    (out_dir / "upload.txt").write_text(
        f"{script.youtube_title}\n\n{script.description}\n\n{' '.join(script.hashtags)}\n",
        encoding="utf-8",
    )
    print(f"\n완료! 영상: {final}")
    print(f"업로드용 제목/설명: {out_dir / 'upload.txt'}")
    print(f"대본 수정 후 다시 만들기: python -m shorts_maker --from-script {out_dir / 'script.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
