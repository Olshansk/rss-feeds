"""Read Anthropic team listings and preserve identities across their URL migration."""

import json
import re
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from feed_history import load_feed_history, merge_feed_history


def parse_team_listing(html, team=None):
    """Extract the current listing without importing recommendation graphs.

    How:
    1. Decode and join the inline Flight transport chunks.
    2. Read only initialPage.posts, excluding related and featured articles.
    3. Validate every fresh item before returning its source metadata.
    """
    chunks = []
    for script in BeautifulSoup(html, "html.parser").find_all("script"):
        match = re.fullmatch(r"self\.__next_f\.push\((.*)\);?", script.get_text(), re.DOTALL)
        if match:
            payload = json.loads(match[1])
            if len(payload) == 2 and payload[0] == 1 and isinstance(payload[1], str):
                chunks.append(payload[1])
    transport = "".join(chunks)
    marker = re.search(r'"initialPage"\s*:\s*', transport)
    if marker is None:
        return None
    page, _ = json.JSONDecoder().raw_decode(transport[marker.end() :])
    posts = page["posts"]
    if not isinstance(posts, list) or not posts:
        raise ValueError("Anthropic listing contains no fresh posts")
    articles = []
    for post in posts:
        if team is not None and team not in {entry["slug"] for entry in post["cardTeams"]}:
            raise ValueError(f"Article does not belong to Anthropic team {team}")
        title = post["title"].strip()
        slug = (post.get("slug") or {}).get("current")
        article_type = post["articleType"]
        if not title or not (slug or post.get("linkedUrl")) or article_type not in {"research", "news"}:
            raise ValueError("Anthropic article is missing valid title, slug, or type")
        link = urljoin("https://www.anthropic.com", post.get("linkedUrl") or f"/{article_type}/{slug}")
        if urlparse(link).scheme != "https":
            raise ValueError("Anthropic article has an invalid link")
        articles.append(
            {
                "title": title,
                "link": link,
                "description": (post.get("summary") or title).strip(),
                "date": datetime.strptime(post["publishedOn"], "%Y-%m-%d").replace(tzinfo=UTC),
                "category": "Engineering" if team == "engineering" else article_type.title(),
            }
        )
    return articles


def merge_team_history(posts, feed_name):
    """Retain published GUIDs and older entries when Anthropic moves article URLs.

    How:
    1. Map known legacy Engineering and Red Team paths to current research URLs.
    2. Reuse each historical GUID, including when its title also changed.
    3. Merge fresh content with the untouched archive using existing history rules.
    """
    migrated = {}
    # Publisher redirects verified during the October 2026 site migration.
    aliases = {"project-fetch": "project-fetch-robot-dog", "ai-for-cyber-defenders": "building-ai-cyber-defenders"}
    for old in load_feed_history(feed_name):
        url = urlparse(old["link"])
        if url.netloc == "www.anthropic.com" and url.path.startswith("/engineering/"):
            slug = url.path.rsplit("/", 1)[-1]
        elif url.netloc == "red.anthropic.com":
            slug = url.path.removesuffix("index.html").rstrip("/").rsplit("/", 1)[-1]
            slug = aliases.get(slug, slug)
        else:
            continue
        migrated[f"https://www.anthropic.com/research/{slug}"] = old["guid"] or old["link"]
    posts = [{**post, "guid": migrated[post["link"]]} if post["link"] in migrated else post for post in posts]
    return merge_feed_history(posts, feed_name, match_titles=True)
