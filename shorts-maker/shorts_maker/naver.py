"""네이버 블로그 글 가져오기: 제목, 본문 문단, 이미지 URL."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
HEADERS = {"User-Agent": UA, "Referer": "https://m.blog.naver.com/"}


@dataclass
class BlogPost:
    url: str
    title: str
    paragraphs: list[str]
    image_urls: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs)


def parse_blog_url(url: str) -> tuple[str, str | None]:
    """URL에서 (blogId, logNo)를 뽑는다. logNo가 없으면 None (= 최신 글 사용)."""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)

    # naver.me 단축 주소 → 실제 주소로 따라가기
    if parsed.netloc.endswith("naver.me"):
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        return parse_blog_url(resp.url)

    qs = parse_qs(parsed.query)
    if "blogId" in qs:
        return qs["blogId"][0], qs.get("logNo", [None])[0]

    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        raise ValueError(f"네이버 블로그 주소를 인식할 수 없어요: {url}")
    blog_id = parts[0]
    log_no = parts[1] if len(parts) > 1 and parts[1].isdigit() else None
    return blog_id, log_no


def latest_log_no(blog_id: str) -> str:
    """RSS에서 가장 최근 글 번호를 가져온다."""
    resp = requests.get(f"https://rss.blog.naver.com/{blog_id}.xml", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    link = root.findtext("./channel/item/link")
    if not link:
        raise ValueError(f"'{blog_id}' 블로그에서 글을 찾지 못했어요.")
    m = re.search(r"/(\d{6,})", link) or re.search(r"logNo=(\d+)", link)
    if not m:
        raise ValueError(f"RSS 링크에서 글 번호를 찾지 못했어요: {link}")
    return m.group(1)


def _clean(text: str) -> str:
    text = text.replace("​", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _upgrade_image_url(src: str) -> str:
    """썸네일 크기(type=w80_blur 등)를 큰 사이즈로 바꾼다."""
    src = src.split("?")[0]
    return src + "?type=w966"


def parse_post_html(html: str, url: str = "") -> BlogPost:
    soup = BeautifulSoup(html, "html.parser")

    # 제목
    title_el = (
        soup.select_one(".se-title-text")
        or soup.select_one(".se_title .se_textarea")
        or soup.select_one(".pcol1")
        or soup.select_one("h3.tit_h3")
    )
    title = _clean(title_el.get_text(" ")) if title_el else ""
    if not title:
        og = soup.find("meta", property="og:title")
        title = _clean(og["content"]) if og and og.get("content") else "제목 없음"

    # 본문 컨테이너 (스마트에디터 ONE → 구버전 순)
    body = (
        soup.select_one(".se-main-container")
        or soup.select_one("#postViewArea")
        or soup.select_one(".post_ct")
        or soup.body
        or soup
    )

    paragraphs: list[str] = []
    blocks = body.select(".se-text-paragraph, .se-quote, p")
    for el in blocks:
        # 중첩 매칭으로 같은 문장이 두 번 들어가는 것 방지
        if el.find_parent(class_="se-text-paragraph"):
            continue
        t = _clean(el.get_text(" "))
        if t and (not paragraphs or paragraphs[-1] != t):
            paragraphs.append(t)

    images: list[str] = []
    for img in body.select("img"):
        src = img.get("data-lazy-src") or img.get("data-src") or img.get("src") or ""
        if not src or "pstatic.net" not in src:
            continue
        # 스티커/이모티콘 제외
        if "storep-phinf" in src or "sticker" in src or "se-sticker" in " ".join(img.get("class", [])):
            continue
        full = _upgrade_image_url(src)
        if full not in images:
            images.append(full)

    if not paragraphs:
        raise ValueError("본문을 찾지 못했어요. 비공개 글이거나 주소가 잘못됐을 수 있어요.")
    return BlogPost(url=url, title=title, paragraphs=paragraphs, image_urls=images)


def fetch_post(url: str) -> BlogPost:
    blog_id, log_no = parse_blog_url(url)
    if log_no is None:
        log_no = latest_log_no(blog_id)
    mobile_url = f"https://m.blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
    resp = requests.get(mobile_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return parse_post_html(resp.text, url=f"https://blog.naver.com/{blog_id}/{log_no}")


def download_images(urls: list[str], out_dir: Path, limit: int = 12) -> list[Path]:
    """이미지를 내려받는다. 네이버 이미지 서버는 Referer가 있어야 응답한다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, u in enumerate(urls[:limit]):
        try:
            r = requests.get(u, headers=HEADERS, timeout=20)
            r.raise_for_status()
            if not r.headers.get("Content-Type", "").startswith("image"):
                continue
            ext = ".png" if "png" in r.headers["Content-Type"] else ".jpg"
            p = out_dir / f"img_{i:02d}{ext}"
            p.write_bytes(r.content)
            paths.append(p)
        except requests.RequestException as e:
            print(f"  ! 이미지 다운로드 실패 ({u}): {e}")
    return paths
