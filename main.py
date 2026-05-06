"""
Pocketly Social Listener — entry point.
Run directly or via cron every Monday.
"""

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("listener.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("pocketly.main")


def main(skip_reddit: bool = False, skip_quora: bool = False) -> None:
    from crawler import crawl_reddit, crawl_quora
    from analyzer import analyse
    from report import build_markdown, save_report, save_raw_json, email_report

    logger.info("=== Pocketly Social Listener starting ===")
    posts = []

    if not skip_reddit:
        logger.info("Crawling Reddit…")
        posts += crawl_reddit(days_back=7)

    if not skip_quora:
        logger.info("Crawling Quora…")
        posts += crawl_quora()

    logger.info("Total posts collected: %d", len(posts))

    logger.info("Sending to Claude for analysis…")
    analysis = analyse(posts)

    report_date = datetime.now().strftime("%d %b %Y")
    markdown = build_markdown(analysis, report_date)

    report_path = save_report(markdown)
    save_raw_json(analysis)

    print("\n" + "=" * 60)
    print(markdown)
    print("=" * 60 + "\n")

    email_report(
        markdown,
        subject=f"Pocketly Weekly Social Intelligence — {report_date}",
    )

    logger.info("Done. Report at %s", report_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pocketly Social Listener")
    parser.add_argument("--skip-reddit", action="store_true", help="Skip Reddit crawl")
    parser.add_argument("--skip-quora", action="store_true", help="Skip Quora crawl")
    args = parser.parse_args()

    main(skip_reddit=args.skip_reddit, skip_quora=args.skip_quora)
