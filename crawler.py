"""
Reddit and Quora crawlers for Pocketly social listening.
Reddit: uses the public JSON API — no credentials needed.
Quora:  uses Google search + page scraping.
"""

import time
import logging
import requests
from typing import Optional
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

KEYWORDS = [
    # Brand / competitors
    "Pocketly", "mPocket", "MoneyTap", "TrueBalance", "CreditBee", "MoneyView",
    # Space keywords
    "loan app", "lending app", "instant loan", "personal loan app",
    "salary advance", "credit line app", "payday loan india",
    "fintech loan", "neobank loan", "BNPL india",
]

REDDIT_SUBREDDITS = [
    "india", "IndiaFinance", "personalfinanceindia", "startups",
]


@dataclass
class Post:
    source: str          # "reddit" | "quora"
    url: str
    title: str
    body: str
    author: str
    subreddit_or_topic: str
    score: int
    comment_count: int
    created_utc: datetime
    matched_keywords: list[str] = field(default_factory=list)
    top_comments: list[str] = field(default_factory=list)


# ── Reddit (no-auth public JSON API) ─────────────────────────────────────────

_REDDIT_HEADERS = {
    "User-Agent": "PocketlySocialListener/1.0 (social research tool)",
    "Accept": "application/json",
}


def _keywords_in_text(text: str) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in KEYWORDS if kw.lower() in text_lower]


_rate_limited = False  # global flag — stop all requests if rate limited


def _fetch_reddit_search(subreddit: str, query: str) -> list[dict]:
    """Hit Reddit's public /search.json endpoint — no credentials required."""
    global _rate_limited
    if _rate_limited:
        return []
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {"q": query, "sort": "new", "t": "week", "limit": 25, "restrict_sr": "true"}
    try:
        resp = requests.get(url, params=params, headers=_REDDIT_HEADERS, timeout=15)
        if resp.status_code == 429:
            logger.warning("Reddit rate limit hit — stopping crawl early")
            _rate_limited = True
            return []
        resp.raise_for_status()
        return resp.json().get("data", {}).get("children", [])
    except Exception as exc:
        logger.warning("Reddit JSON API error for r/%s q='%s': %s", subreddit, query, exc)
        return []


def _fetch_top_comments(permalink: str) -> list[str]:
    """Fetch top comments for a post via the public JSON API."""
    url = f"https://www.reddit.com{permalink}.json"
    try:
        resp = requests.get(url, headers=_REDDIT_HEADERS, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        if len(data) < 2:
            return []
        comments = data[1].get("data", {}).get("children", [])
        return [
            c["data"]["body"][:400]
            for c in comments
            if c.get("kind") == "t1" and c.get("data", {}).get("body")
        ][:5]
    except Exception:
        return []


def crawl_reddit(days_back: int = 7) -> list[Post]:
    """Fetch Reddit posts from the past `days_back` days — no API key needed."""
    global _rate_limited
    _rate_limited = False
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    found: dict[str, Post] = {}

    for subreddit in REDDIT_SUBREDDITS:
        if _rate_limited:
            break
        # Search all keywords in one combined query per subreddit
        combined_query = " OR ".join(f'"{kw}"' for kw in KEYWORDS[:6])
        children = _fetch_reddit_search(subreddit, combined_query)
        time.sleep(3)  # generous pause between subreddits

        for child in children:
            d = child.get("data", {})
            post_id = d.get("id", "")
            if not post_id or post_id in found:
                continue

            created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
            if created < cutoff:
                continue

            title = d.get("title", "")
            body = d.get("selftext", "")
            matched = _keywords_in_text(title + " " + body)
            if not matched:
                continue

            top_comments = _fetch_top_comments(d.get("permalink", ""))
            time.sleep(2)

            found[post_id] = Post(
                source="reddit",
                url=f"https://reddit.com{d.get('permalink', '')}",
                title=title,
                body=body[:1000],
                author=d.get("author", ""),
                subreddit_or_topic=subreddit,
                score=d.get("score", 0),
                comment_count=d.get("num_comments", 0),
                created_utc=created,
                matched_keywords=matched,
                top_comments=top_comments,
            )

    logger.info("Reddit: collected %d posts", len(found))
    return list(found.values())


# ── Quora ─────────────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _google_quora_urls(keyword: str, num_results: int = 5) -> list[str]:
    """Use Google to find Quora pages discussing a keyword (avoids Quora login wall)."""
    query = f'site:quora.com "{keyword}"'
    url = "https://www.google.com/search"
    params = {"q": query, "num": num_results, "hl": "en"}
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        links = []
        for a in soup.select("a[href]"):
            href = a["href"]
            if "quora.com" in href and "/question/" in href:
                # strip Google redirect wrapper
                if href.startswith("/url?q="):
                    href = href.split("/url?q=")[1].split("&")[0]
                if href not in links:
                    links.append(href)
        return links[:num_results]
    except Exception as exc:
        logger.warning("Google/Quora search failed for '%s': %s", keyword, exc)
        return []


def _scrape_quora_page(url: str) -> Optional[Post]:
    """Scrape visible text from a Quora question page."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        title_el = soup.find("span", class_=lambda c: c and "question" in c.lower())
        title = title_el.get_text(strip=True) if title_el else soup.title.string or url

        # Grab all visible answer snippets
        answer_texts = [
            el.get_text(" ", strip=True)[:400]
            for el in soup.select("div.q-box span.q-text")
            if len(el.get_text(strip=True)) > 80
        ][:5]

        body = " … ".join(answer_texts) if answer_texts else ""
        matched = _keywords_in_text(title + " " + body)
        if not matched:
            return None

        return Post(
            source="quora",
            url=url,
            title=title[:200],
            body=body[:1000],
            author="quora_user",
            subreddit_or_topic="Quora",
            score=0,
            comment_count=len(answer_texts),
            created_utc=datetime.now(timezone.utc),
            matched_keywords=matched,
            top_comments=answer_texts,
        )
    except Exception as exc:
        logger.warning("Failed to scrape Quora page %s: %s", url, exc)
        return None


def crawl_quora() -> list[Post]:
    """Search Quora (via Google) for keyword discussions."""
    seen_urls: set[str] = set()
    posts: list[Post] = []

    for keyword in KEYWORDS:
        urls = _google_quora_urls(keyword)
        for url in urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            post = _scrape_quora_page(url)
            if post:
                posts.append(post)
            time.sleep(1)   # be polite

    logger.info("Quora: collected %d posts", len(posts))
    return posts
