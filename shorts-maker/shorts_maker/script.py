"""Claude로 블로그 글을 쇼츠 대본(장면별 내레이션 + 자막 + 이미지 배치)으로 바꾼다."""
from __future__ import annotations

import base64
import io
from pathlib import Path

import anthropic
from PIL import Image
from pydantic import BaseModel, Field

from .naver import BlogPost

MODEL = "claude-opus-5-5"


class Scene(BaseModel):
    narration: str = Field(description="이 장면에서 읽을 내레이션. 한두 문장, 구어체.")
    caption: str = Field(description="화면에 크게 띄울 짧은 자막 (20자 이내 권장)")
    image_index: int = Field(description="사용할 이미지 번호(0부터). 이미지가 없거나 맞는 게 없으면 -1")


class ShortsScript(BaseModel):
    title: str = Field(description="영상 상단에 고정으로 띄울 제목 (15자 이내)")
    scenes: list[Scene]
    youtube_title: str = Field(description="업로드용 제목 (#Shorts 포함)")
    description: str = Field(description="업로드용 설명 2~3줄")
    hashtags: list[str]


SYSTEM = """당신은 한국어 유튜브 쇼츠/인스타 릴스 대본 작가입니다.
블로그 글을 받아 30~50초 분량의 세로 영상 대본으로 바꿉니다.

규칙:
- 첫 장면은 시청자가 넘기지 않도록 강한 훅(질문, 놀라운 사실, 공감 포인트)으로 시작합니다.
- 장면은 6~9개. 각 내레이션은 한두 문장, 말하듯 자연스럽게 씁니다.
- 블로그에 없는 사실을 지어내지 않습니다. 수치·가격·날짜는 원문 그대로 씁니다.
- 마지막 장면은 짧은 마무리와 행동 유도(저장, 팔로우, 블로그에서 자세히 보기 등)로 끝냅니다.
- 이미지가 주어지면 각 장면 내용과 가장 잘 맞는 이미지 번호를 고르고, 같은 이미지는 되도록 반복하지 않습니다.
- 자막(caption)은 내레이션의 핵심 키워드만 짧게 씁니다. 이모지는 쓰지 않습니다."""


def _image_block(path: Path) -> dict:
    img = Image.open(path).convert("RGB")
    img.thumbnail((768, 768))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.b64encode(buf.getvalue()).decode(),
        },
    }


def write_script(post: BlogPost, images: list[Path], extra_instructions: str = "") -> ShortsScript:
    client = anthropic.Anthropic()

    content: list[dict] = []
    for i, p in enumerate(images):
        content.append({"type": "text", "text": f"[이미지 {i}]"})
        content.append(_image_block(p))

    body = post.text
    if len(body) > 30000:
        print("  ! 글이 매우 길어 앞부분 30,000자만 사용합니다.")
        body = body[:30000]

    prompt = (
        f"블로그 제목: {post.title}\n"
        f"블로그 주소: {post.url}\n"
        f"사용 가능한 이미지 수: {len(images)}\n\n"
        f"<blog>\n{body}\n</blog>\n\n"
        "위 글로 쇼츠 대본을 만들어 주세요."
    )
    if extra_instructions:
        prompt += f"\n\n추가 요청: {extra_instructions}"
    content.append({"type": "text", "text": prompt})

    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        output_config={"effort": "medium"},
        # 안전 분류기가 요청을 거절하면 서버가 다른 모델로 자동 재시도
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": content}],
        output_format=ShortsScript,
    )

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude가 이 글의 대본 작성을 거절했어요.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("대본이 너무 길어 중간에 잘렸어요. 다시 시도해 주세요.")

    script = response.parsed_output
    # 범위를 벗어난 이미지 번호 정리
    for s in script.scenes:
        if not (0 <= s.image_index < len(images)):
            s.image_index = -1
    return script
