"""
Claude-powered analysis of crawled social posts.
Produces a structured weekly intelligence report for Pocketly.
"""

import json
import anthropic
from crawler import Post

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a senior product and growth strategist for Pocketly —
a consumer lending / fintech app in India. Your job is to analyse raw social media
discussions scraped from Reddit and Quora and turn them into crisp, actionable
weekly intelligence for the founding team.

Always be direct, specific, and commercially minded.
Avoid generic platitudes. Prioritise signal over noise."""


def _posts_to_text(posts: list[Post]) -> str:
    lines = []
    for i, p in enumerate(posts, 1):
        lines.append(
            f"[{i}] SOURCE={p.source} | SUBREDDIT/TOPIC={p.subreddit_or_topic} | "
            f"SCORE={p.score} | COMMENTS={p.comment_count} | "
            f"KEYWORDS={','.join(p.matched_keywords)}\n"
            f"TITLE: {p.title}\n"
            f"BODY: {p.body}\n"
            f"TOP COMMENTS: {' | '.join(p.top_comments[:3])}\n"
            f"URL: {p.url}\n"
        )
    return "\n---\n".join(lines)


ANALYSIS_PROMPT = """\
Below are social media posts from the past 7 days discussing Pocketly, our \
competitors (mPocket, MoneyTap, TrueBalance, CreditBee, MoneyView), or the \
broader lending/loan-app space in India.

<posts>
{posts_text}
</posts>

Produce a report in the following exact JSON structure (no markdown, pure JSON):

{{
  "executive_summary": "3-4 sentence paragraph capturing the week's most important signal",

  "brand_mentions": {{
    "pocketly": {{
      "count": <int>,
      "sentiment": "positive|neutral|negative|mixed",
      "key_themes": ["theme1", "theme2"],
      "notable_quotes": ["quote1", "quote2"]
    }},
    "competitors": [
      {{
        "name": "<competitor name>",
        "count": <int>,
        "sentiment": "positive|neutral|negative|mixed",
        "what_users_love": ["point1"],
        "what_users_hate": ["point1"]
      }}
    ]
  }},

  "user_pain_points": [
    {{
      "pain_point": "<concise label>",
      "frequency": "high|medium|low",
      "verbatim": "<representative user quote>",
      "opportunity_for_pocketly": "<specific product/UX improvement>"
    }}
  ],

  "emerging_trends": [
    {{
      "trend": "<label>",
      "description": "<2 sentences>",
      "pocketly_implication": "<what this means for us>"
    }}
  ],

  "competitor_weaknesses": [
    {{
      "competitor": "<name>",
      "weakness": "<label>",
      "evidence": "<user quote or observation>",
      "how_pocketly_can_exploit": "<specific action>"
    }}
  ],

  "action_items": [
    {{
      "priority": "P1|P2|P3",
      "team": "Product|Marketing|Growth|CX|Risk",
      "action": "<crisp one-liner>",
      "rationale": "<why now, based on this week's data>",
      "effort": "small|medium|large"
    }}
  ],

  "content_opportunities": [
    {{
      "platform": "Reddit|Quora|Both",
      "thread_url": "<url or null>",
      "suggested_response_angle": "<how Pocketly should engage authentically>"
    }}
  ],

  "week_score": {{
    "overall_sentiment_score": <1-10 where 10 is very positive>,
    "buzz_volume": "low|medium|high",
    "risk_flags": ["<any reputation or regulatory risk worth flagging>"]
  }}
}}"""


def analyse(posts: list[Post]) -> dict:
    """Send posts to Claude and get back structured analysis."""
    if not posts:
        return {"error": "No posts collected this week.", "posts_analysed": 0}

    posts_text = _posts_to_text(posts)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": ANALYSIS_PROMPT.format(posts_text=posts_text),
            }
        ],
    )

    raw = response.content[0].text.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]

    result = json.loads(raw)
    result["posts_analysed"] = len(posts)
    return result
