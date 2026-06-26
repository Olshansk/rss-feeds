"""Generate RSS feed for Hugging Face Blog posts tagged research."""

import argparse

from huggingface_blog_common import run_tag_feed
from utils import setup_logging

logger = setup_logging()

FEED_NAME = "huggingface_research"
BLOG_URL = "https://huggingface.co/blog?tag=research"
TAG = "research"


def main(full_reset: bool = False) -> bool:
    return run_tag_feed(
        tag=TAG,
        feed_name=FEED_NAME,
        blog_url=BLOG_URL,
        feed_title="Hugging Face Blog (Research)",
        feed_description="Research posts from the Hugging Face blog",
        full_reset=full_reset,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Hugging Face research blog RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (fetch all tagged posts)")
    args = parser.parse_args()
    main(full_reset=args.full)
