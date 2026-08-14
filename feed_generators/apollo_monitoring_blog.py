"""Generate an RSS feed for Apollo Research's Monitoring section.

https://www.apolloresearch.ai/monitoring/
"""

from apollo_common import BASE_URL, run_section

FEED_NAME = "apollo_monitoring"
BLOG_URL = f"{BASE_URL}/monitoring/"


def main():
    return run_section(
        section="monitoring",
        feed_name=FEED_NAME,
        feed_title="Apollo Research - Monitoring",
        feed_description="Publications from Apollo Research's Monitoring section",
        blog_url=BLOG_URL,
    )


if __name__ == "__main__":
    main()
