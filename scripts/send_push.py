"""Supabase에 저장된 구독자에게 오늘의 소식을 웹푸시로 보낸다.

사용법: python send_push.py digests/claude/2026-10-05.json
환경변수: SUPABASE_URL, SUPABASE_SERVICE_KEY, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT
         SITE_NAME(선택), DRY_RUN=1(실제 발송 없이 대상·내용만 출력)
- 구독자가 고른 관심 분야에 오늘 소식이 없으면 보내지 않는다.
- 구독이 끊긴 사람(404/410)은 자동으로 목록에서 지운다.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import webpush
from common import SECTION_TITLES, load_json, page_name, site_url

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SITE_NAME = os.environ.get("SITE_NAME") or "레고 데일리"
ALL_TOPICS = ["kr_deal", "new_release", "kr_news", "global_news"]


def sb(method, path, body=None):
    h = {"apikey": SB_KEY, "Content-Type": "application/json", "Prefer": "return=minimal"}
    if SB_KEY.startswith("eyJ"):  # 예전 형식(JWT) 키는 Authorization 헤더도 필요
        h["Authorization"] = f"Bearer {SB_KEY}"
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", method=method, headers=h,
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else None


def all_subscribers():
    out, offset = [], 0
    while True:
        rows = sb("GET", f"push_subscribers?select=id,endpoint,p256dh,auth,topics&order=created_at"
                         f"&limit=1000&offset={offset}")
        out += rows
        if len(rows) < 1000:
            return out
        offset += 1000


def message_for(d, topics):
    """구독자 관심 분야에 맞춘 알림 내용. 해당 소식이 없으면 None."""
    md = f"{int(d['date'][5:7])}/{int(d['date'][8:10])}"
    picked = []
    for order, sec in enumerate(d.get("sections", [])):
        if sec["key"] in topics:
            for i, it in enumerate(sec.get("items", [])):
                picked.append((-int(it.get("importance", 1) or 1), order, it, f"{sec['key']}-{i}"))
    if not picked:
        return None
    picked.sort(key=lambda x: (x[0], x[1]))
    top, anchor = picked[0][2], picked[0][3]
    n = len(picked)
    use_headline = bool(d.get("headline")) and set(topics) >= {"kr_deal", "new_release"}
    body = d["headline"] if use_headline else top["title"]
    if n > 1 and not use_headline:
        body += f" (외 {n - 1}건)"
    msg = {
        "title": f"🧱 {SITE_NAME} {md} · 새 소식 {n}건",
        "body": body[:150],
        "url": f"{site_url()}/{page_name(d)}?src=push" + ("" if use_headline else f"#{anchor}"),
        "icon": f"{site_url()}/icon-192.png",
        "tag": f"daily-{d['date']}",
    }
    if top.get("image"):
        msg["image"] = top["image"]
    return msg


def main():
    d = load_json(sys.argv[1])
    if not d:
        sys.exit("다이제스트 없음")
    if not (SB_URL and SB_KEY and os.environ.get("VAPID_PRIVATE_KEY")):
        print("웹푸시 설정 없음 → 건너뜀")
        return
    subs = all_subscribers()
    jobs = []
    for s in subs:
        msg = message_for(d, s.get("topics") or ALL_TOPICS)
        if msg:
            jobs.append((s, msg))
    print(f"구독자 {len(subs)}명 중 오늘 보낼 대상 {len(jobs)}명")
    if os.environ.get("DRY_RUN"):
        for s, m in jobs[:5]:
            print(json.dumps(m, ensure_ascii=False))
        return

    priv = webpush.load_private_key(os.environ["VAPID_PRIVATE_KEY"])
    pub = os.environ["VAPID_PUBLIC_KEY"].strip()
    subject = os.environ.get("VAPID_SUBJECT") or "mailto:admin@example.com"

    def one(job):
        s, m = job
        return s["id"], webpush.send(s, m, priv, pub, subject)

    with ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(one, jobs))
    ok = sum(1 for _, c in results if 200 <= c < 300)
    gone = [i for i, c in results if c in (404, 410)]
    other = [(i, c) for i, c in results if not (200 <= c < 300) and c not in (404, 410)]
    for i in range(0, len(gone), 100):
        ids = ",".join(gone[i:i + 100])
        sb("DELETE", f"push_subscribers?id=in.({urllib.parse.quote(ids)})")
    print(f"웹푸시 완료: 성공 {ok} / 해지되어 삭제 {len(gone)} / 기타 실패 {len(other)}")
    if other:
        print("기타 실패 예시(상태코드):", sorted({c for _, c in other}))


if __name__ == "__main__":
    main()
