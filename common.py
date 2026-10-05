"""공통 설정: 섹션 정의, 다이제스트(JSON) 입출력."""
import json
import os
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 다이제스트 섹션 (key, 제목) — Claude 요약/자동 스크립트 모두 이 key를 사용
SECTIONS = [
    ("kr_deal", "🏷️ 국내 할인"),
    ("kr_news", "🇰🇷 국내 소식"),
    ("global_news", "🌍 해외 소식"),
    ("new_release", "🆕 신제품 발매"),
]
SECTION_TITLES = dict(SECTIONS)
SOURCE_LABELS = {"claude": "Claude 요약", "rss": "자동 수집"}


def today_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def digest_path(source: str, date: str) -> str:
    return os.path.join(ROOT, "digests", source, f"{date}.json")


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def site_url() -> str:
    """GitHub Pages 주소. SITE_URL 환경변수가 있으면 우선."""
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "owner/lego-kakao-bot")
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}"


def page_name(digest: dict) -> str:
    return f"{digest['date']}-{digest['source']}.html"
