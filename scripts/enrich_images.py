"""다이제스트 항목마다 원문 페이지의 대표 이미지(og:image)를 찾아 'image' 필드로 넣는다.
웹페이지 썸네일과 카톡 리스트 메시지 이미지에 쓰인다. 실패해도 그냥 넘어간다.

사용법: python enrich_images.py digests/claude/2026-10-05.json
"""
import html
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from common import load_json, save_json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
SKIP_HOSTS = ("news.google.com",)
OG_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::src)?["\'][^>]*content=["\']([^"\']+)["\']'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image)["\']', re.I)


def find_image(url):
    try:
        if urllib.parse.urlparse(url).hostname in SKIP_HOSTS:
            return None
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            head = r.read(300_000).decode("utf-8", errors="ignore")
            final = r.geturl()
        m = OG_RE.search(head)
        if not m:
            return None
        img = html.unescape(m.group(1) or m.group(2)).strip()
        img = urllib.parse.urljoin(final, img)
        return img if img.startswith("https://") else None
    except Exception:
        return None


def main():
    path = sys.argv[1]
    d = load_json(path)
    if not d:
        return
    items = [it for s in d.get("sections", []) for it in s.get("items", []) if not it.get("image")]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for it, img in zip(items, ex.map(lambda it: find_image(it["url"]), items)):
            if img:
                it["image"] = img
    save_json(path, d)
    print(f"이미지 찾음: {sum(1 for it in items if it.get('image'))}/{len(items)}")


if __name__ == "__main__":
    main()
