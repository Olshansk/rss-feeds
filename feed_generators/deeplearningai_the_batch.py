"""Mirror The Batch's official publisher feed while retaining subscriber history."""

from urllib.parse import urlparse

from feed_history import merge_feed_history
from native_rss import generate_feed, parse_rss
from utils import fetch_page, save_rss_feed

FEED_NAME = "the_batch"
BLOG_URL = "https://www.deeplearning.ai/the-batch/"
SOURCE_URL = "https://charonhub.deeplearning.ai/tag/the-batch/rss/"


def parse_batch_feed(content):
    """Map publisher RSS records to the public article URLs already used by readers.

    How:
    1. Parse the publisher's dedicated Batch feed using strict native RSS rules.
    2. Validate publisher links and map their slugs to the public Batch website.
    3. Use canonical article URLs as identities before merging published history.
    """
    posts = parse_rss(content)
    for post in posts:
        source = urlparse(post["link"])
        if source.hostname != "charonhub.deeplearning.ai":
            raise ValueError(f"Unexpected Batch publisher link: {post['link']}")
        post["link"] = BLOG_URL.rstrip("/") + source.path.rstrip("/")
        post["guid"] = post["link"]
    return posts


def main():
    """Refresh the publisher's latest issues and retain the complete saved archive.

    How:
    1. Fetch and validate the official, limited-window publisher RSS feed.
    2. Merge fresh records into published history without changing existing IDs.
    3. Build and atomically validate the subscriber feed before publication.
    """
    posts = merge_feed_history(parse_batch_feed(fetch_page(SOURCE_URL)), FEED_NAME, match_titles=True)
    feed = generate_feed(
        posts,
        title="The Batch | DeepLearning.AI",
        description="Weekly AI news and insights from DeepLearning.AI's The Batch.",
        blog_url=BLOG_URL,
        feed_name=FEED_NAME,
    )
    save_rss_feed(feed, FEED_NAME)
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Refresh The Batch from the official publisher RSS feed")
    parser.add_argument(
        "--full", action="store_true", help="Refresh available publisher issues; saved archive is retained"
    )
    parser.parse_args()
    raise SystemExit(0 if main() else 1)
