"""네이버 뉴스검색(최신순)에서 Claude AI / Anthropic 관련 기사를 골라냅니다.

검색 결과 페이지에 들어 있는 기사 데이터(JSON)를 읽으므로 API 키가 필요 없습니다.
제목에 키워드가 있는 기사만 고르고, 여러 언론사가 같은 소식을 낸 경우 비슷한 제목은 한 번만 보냅니다.
"""
import difflib
import html
import json
import re
import urllib.parse
import urllib.request

QUERIES = ["앤트로픽", "엔트로픽", "Anthropic", "클로드 AI"]
SEARCH_URL = "https://search.naver.com/search.naver?where=news&sort=1&query="
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

# 회사명은 제목에 있으면 바로 알림
COMPANY = re.compile(r"앤트로픽|엔트로픽|anthropic", re.IGNORECASE)
# '클로드'는 모네·드뷔시 같은 인물과 겹치므로 AI 관련 단어가 함께 있을 때만
CLAUDE = re.compile(r"클로드|claude", re.IGNORECASE)
AI_CONTEXT = re.compile(r"AI|인공지능|챗봇|LLM|모델|오퍼스|오푸스|소네트|하이쿠|opus|sonnet|haiku|코딩|에이전트",
                        re.IGNORECASE)

SIMILAR_TITLE = 0.6  # 이 이상 비슷한 제목은 같은 소식으로 봄

_ITEM = re.compile(r'"content":"((?:[^"\\]|\\.)*)","contentHref":"((?:[^"\\]|\\.)*)"')
_TITLE = re.compile(r'"title":"((?:[^"\\]|\\.)*)","titleHref":"((?:[^"\\]|\\.)*)","type":"searchBasic"')
_PRESS = re.compile(r'"title":"((?:[^"\\]|\\.)*)","titleHref":"[^"]*"\},"title":"')


def _unescape(s):
    s = json.loads(f'"{s}"')
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def parse(page):
    """검색 결과 HTML에서 기사 목록 [{title, url, content, press}]를 뽑습니다."""
    titles = {_unescape(u): _unescape(t) for t, u in _TITLE.findall(page)}
    items = {}
    for m in _ITEM.finditer(page):
        url = _unescape(m.group(2))
        if url not in titles or url in items:
            continue
        # 언론사 이름은 같은 기사 블록 안 sourceProfile에 있음
        block = page[m.end():m.end() + 6000]
        press = _PRESS.search(block)
        items[url] = {
            "title": titles[url], "url": url, "content": _unescape(m.group(1)),
            "press": _unescape(press.group(1)) if press else "",
        }
    return list(items.values())


def is_relevant(item):
    title = item["title"]
    if COMPANY.search(title):
        return True
    return bool(CLAUDE.search(title) and (AI_CONTEXT.search(title) or COMPANY.search(item["content"])))


def fetch(query):
    req = urllib.request.Request(SEARCH_URL + urllib.parse.quote(query), headers={
        "User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "ignore")


def _norm(title):
    return re.sub(r"[\W_]+", "", title.lower())


def check(state, send, dry_run=False):
    """새 관련 기사를 send(item)으로 보냅니다. 상태가 없으면(첫 실행) 현재 기사는 본 것으로만 기록합니다."""
    first_run = state is None
    state = state or {"urls": [], "titles": []}
    seen_urls, recent_titles = set(state["urls"]), list(state["titles"])

    items = []
    for q in QUERIES:
        items.extend(parse(fetch(q)))

    for item in items:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        state["urls"].append(item["url"])
        if not is_relevant(item):
            continue
        norm = _norm(item["title"])
        if any(difflib.SequenceMatcher(None, norm, t).ratio() >= SIMILAR_TITLE for t in recent_titles):
            continue
        recent_titles.append(norm)
        if first_run and not dry_run:
            continue
        print(f"[네이버] {item['press']}  {item['title']}", flush=True)
        if not dry_run:
            try:
                send(item)
            except Exception as e:  # 알림 실패해도 다음 기사는 계속
                print(f"  알림 전송 실패: {e}", flush=True)

    return {"urls": state["urls"][-1000:], "titles": recent_titles[-200:]}
