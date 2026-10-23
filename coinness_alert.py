#!/usr/bin/env python3
"""코인니스 속보 중 관심 코인 / 상장폐지 소식만 골라 휴대폰으로 알림을 보냅니다.

알림 채널 (환경변수로 설정, 둘 다 설정하면 둘 다 보냄)
  NTFY_TOPIC          ntfy 앱에서 구독할 토픽 이름 (예: coinness-pro-8f3k2)
  TELEGRAM_BOT_TOKEN  텔레그램 봇 토큰
  TELEGRAM_CHAT_ID    텔레그램 chat id

실행
  python3 coinness_alert.py          # 1분마다 계속 확인 (PC/서버에서 상시 실행)
  python3 coinness_alert.py --once   # 한 번만 확인 (GitHub Actions 등 스케줄러용)
  python3 coinness_alert.py --test   # 최근 속보로 필터 결과만 출력, 알림 안 보냄
"""
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

API_URL = "https://api.coinness.com/feed/v1/breaking-news?languageCode=ko&limit=50"
STATE_FILE = os.environ.get("STATE_FILE", "coinness_seen.json")
POLL_SECONDS = 60
# 상태 파일이 없을 때(첫 실행) 이 시간 이내 속보만 알림 (옛날 소식 폭탄 방지)
FIRST_RUN_WINDOW = timedelta(minutes=int(os.environ.get("FIRST_RUN_MINUTES", "15")))

# 관심 코인: 티커 -> 본문/제목에서 찾을 이름들
# '온도', '수이', '니어' 단독은 일반 단어(온도, 엔지니어 등)와 겹쳐서 제외하고 티커/정식명으로만 찾습니다.
COINS = {
    "NEAR": ["니어프로토콜", "니어 프로토콜", "NEAR Protocol"],
    "HBAR": ["헤데라", "Hedera"],
    "ONDO": ["온도파이낸스", "온도 파이낸스", "Ondo"],
    "ALGO": ["알고랜드", "Algorand"],
    "LINK": ["체인링크", "Chainlink"],
    "AVAX": ["아발란체", "Avalanche"],
    "SUI": ["수이 네트워크", "수이네트워크"],
    "DOGE": ["도지코인", "Dogecoin"],
}

DELIST_KEYWORDS = [
    "상장폐지", "상폐", "거래지원 종료", "거래 지원 종료", "거래지원종료",
    "유의종목", "유의 종목", "디리스팅", "delist",
]


def _word(term):
    # 영문은 단어 경계로 찾음 (LINK가 LINKED에, SUI가 SUIT에 걸리지 않도록)
    if re.fullmatch(r"[A-Za-z ]+", term):
        return r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])"
    return re.escape(term)


# 티커는 대문자 그대로만(영문 link 같은 일반 단어 제외), 이름은 대소문자 무시
COIN_PATTERNS = {
    code: re.compile(_word(code) + "|(?i:" + "|".join(_word(n) for n in names) + ")")
    for code, names in COINS.items()
}
DELIST_PATTERN = re.compile("|".join(map(re.escape, DELIST_KEYWORDS)), re.IGNORECASE)


def match(item):
    """알림 사유 목록을 돌려줍니다. 빈 목록이면 알림 대상 아님."""
    codes = {c.upper() for c in (item.get("originCodes") or [])}
    if item.get("quickOrderCode"):
        codes.add(item["quickOrderCode"].upper())
    text = f"{item.get('title') or ''}\n{item.get('content') or ''}"

    reasons = [code for code, pat in COIN_PATTERNS.items() if code in codes or pat.search(text)]
    if DELIST_PATTERN.search(text):
        reasons.append("상장폐지")
    return reasons


def fetch_news():
    req = urllib.request.Request(API_URL, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Origin": "https://coinness.com",
        "Referer": "https://coinness.com/",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()


def notify(item, reasons):
    title = f"[{', '.join(reasons)}] {item.get('title') or ''}".strip()
    body = (item.get("content") or "").strip()
    if len(body) > 700:
        body = body[:700] + "…"
    link = f"https://coinness.com/news/{item['id']}"

    topic = os.environ.get("NTFY_TOPIC")
    if topic:
        server = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
        post(server, {
            "topic": topic, "title": title[:250], "message": body or title,
            "click": link, "priority": 5 if "상장폐지" in reasons else 4,
        })

    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        post(f"https://api.telegram.org/bot{token}/sendMessage", {
            "chat_id": chat, "text": f"{title}\n\n{body}\n\n{link}",
            "disable_web_page_preview": True,
        })


def load_seen():
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, ValueError):
        return None


def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(seen)[-500:], f)


def check(seen, dry_run=False):
    items = fetch_news()
    first_run = seen is None
    seen = set() if seen is None else seen
    now = datetime.now(timezone.utc)

    for item in sorted(items, key=lambda x: x["id"]):
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        reasons = match(item)
        if not reasons:
            continue
        if first_run and not dry_run:
            published = datetime.fromisoformat(item["publishAt"])
            if now - published > FIRST_RUN_WINDOW:
                continue
        print(f"{item['publishAt']}  [{', '.join(reasons)}] {item.get('title')}", flush=True)
        if not dry_run:
            try:
                notify(item, reasons)
            except Exception as e:  # 알림 실패해도 다음 소식은 계속
                print(f"  알림 전송 실패: {e}", file=sys.stderr)
    return seen


def main():
    args = set(sys.argv[1:])
    if "--test" in args:
        check(None, dry_run=True)
        return
    if not (os.environ.get("NTFY_TOPIC") or os.environ.get("TELEGRAM_BOT_TOKEN")):
        sys.exit("NTFY_TOPIC 또는 TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 환경변수를 설정하세요.")

    seen = load_seen()
    while True:
        try:
            seen = check(seen)
            save_seen(seen)
        except Exception as e:
            print(f"확인 실패: {e}", file=sys.stderr)
        if "--once" in args:
            break
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
