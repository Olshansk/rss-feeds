"""Generate an RSS feed for Apollo Research's Science section.

https://www.apolloresearch.ai/science/
"""

from apollo_common import BASE_URL, run_section

FEED_NAME = "apollo_science"
BLOG_URL = f"{BASE_URL}/science/"


def main():
    return run_section(
        section="science",
        feed_name=FEED_NAME,
        feed_title="Apollo Research - Science",
        feed_description="Research publications from Apollo Research's Science section",
        blog_url=BLOG_URL,
    )


if __name__ == "__main__":
    main()
