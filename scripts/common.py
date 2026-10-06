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
    if (os.environ.get("SITE_URL") or "").strip():
        return os.environ["SITE_URL"].strip().rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "owner/lego-kakao-bot")
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}"


def page_name(digest: dict) -> str:
    return f"{digest['date']}-{digest['source']}.html"


# ---------- 항목 주소 (웹페이지·카톡·푸시가 같은 규칙을 씀) ----------
NEWS_KEYS = ("kr_news", "global_news")   # 브릭소리 자체 요약 페이지를 만드는 섹션
POOL_PAGES = {"kr_deal": "deals.html", "new_release": "releases.html"}  # 기간 동안 모아 보여주는 섹션
POOL_PREFIX = {"kr_deal": "d", "new_release": "r"}


def item_id(it: dict) -> str:
    import hashlib
    key = (it.get("url") or it.get("title") or "").strip().lower()
    return hashlib.sha1(key.encode()).hexdigest()[:8]


def news_page(date: str, it: dict) -> str:
    return f"n-{date}-{item_id(it)}.html"


def item_link(d: dict, key: str, it: dict) -> str:
    """사이트 안에서 이 항목을 보여주는 상대 주소."""
    if key in NEWS_KEYS:
        return news_page(d["date"], it)
    if key in POOL_PAGES:
        return f"{POOL_PAGES[key]}#{POOL_PREFIX[key]}-{item_id(it)}"
    return f"{page_name(d)}#{key}"
