"""Generate an RSS feed for Apollo Research's Governance section.

https://www.apolloresearch.ai/governance/
"""

from apollo_common import BASE_URL, run_section

FEED_NAME = "apollo_governance"
BLOG_URL = f"{BASE_URL}/governance/"


def main():
    return run_section(
        section="governance",
        feed_name=FEED_NAME,
        feed_title="Apollo Research - Governance",
        feed_description="Publications from Apollo Research's Governance section",
        blog_url=BLOG_URL,
    )


if __name__ == "__main__":
    main()
