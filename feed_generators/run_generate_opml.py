"""Generate an OPML file for the repository's RSS feeds."""

import argparse
import logging
import tomllib
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path

from models import GlobalSettings
from utils import get_feeds_dir, get_project_root

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


DEFAULT_OUTPUT = "feeds/feeds.opml"
OPML_DOCS_URL = "https://opml.org/spec2.opml"
RSS_VERSION = "RSS2.0"
ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
DEFAULT_XML_URL_ANCHOR = ""


def format_opml_time(value: datetime) -> str:
    """Format a datetime in the RFC 2822 format used by OPML."""
    return format_datetime(value, usegmt=True)


def read_pyproject_authors() -> list[dict[str, str]]:
    """Read project authors from pyproject.toml."""
    pyproject_path = get_project_root() / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    return pyproject.get("project", {}).get("authors", [])


def resolve_owner(repo_slug: str) -> dict[str, str]:
    """Resolve OPML owner fields from the repo owner and pyproject authors."""
    owner_id = repo_slug.split("/", 1)[0]
    authors = read_pyproject_authors()
    owner_names = [author["name"] for author in authors if author.get("name")]
    owner_emails = [author["email"] for author in authors if author.get("email")]

    return {
        "ownerId": owner_id,
        "ownerName": ", ".join(owner_names) if owner_names else owner_id,
        "ownerEmail": ", ".join(owner_emails),
    }


def format_opml_title(repo_slug: str) -> str:
    """Format the repository slug for OPML display fields."""
    return repo_slug.replace("/", "-")


def find_atom_self_url(channel: ET.Element) -> str:
    """Find the atom:link rel=self URL for an RSS channel."""
    for atom_link in channel.findall(f"{{{ATOM_NAMESPACE}}}link"):
        if atom_link.attrib.get("rel") == "self" and atom_link.attrib.get("href"):
            return atom_link.attrib["href"].strip()
    return ""


def default_feed_xml_url(feed_file: Path, repo_slug: str) -> str:
    """Build the default raw GitHub feed URL from a feed XML filename."""
    return f"https://raw.githubusercontent.com/{repo_slug}/main/feeds/{feed_file.name}"


def format_xml_url(xml_url: str, xml_url_anchor: str) -> str:
    """Format an OPML xmlUrl, optionally appending an anchor fragment."""
    if xml_url_anchor:
        return f"{xml_url}#{xml_url_anchor.lstrip('#')}"
    return xml_url


def read_feed_metadata(feed_file: Path, repo_slug: str, xml_url_anchor: str) -> dict[str, str]:
    """Read OPML outline metadata from an RSS XML file."""
    try:
        root = ET.parse(feed_file).getroot()
    except ET.ParseError as exc:
        logger.warning("Could not parse %s: %s", feed_file, exc)
        return {}

    channel = root.find("channel")
    if channel is None:
        return {}

    title = (channel.findtext("title") or "").strip()
    xml_url = find_atom_self_url(channel)
    if not xml_url:
        xml_url = default_feed_xml_url(feed_file, repo_slug)
        logger.warning("Using default xmlUrl for %s because atom:link rel=self is missing", feed_file)

    if not title:
        logger.warning("Skipping %s because channel title is missing", feed_file)
        return {}

    return {
        "type": "rss",
        "text": title,
        "title": title,
        "xmlUrl": format_xml_url(xml_url, xml_url_anchor),
        "description": (channel.findtext("description") or "").strip(),
        "htmlUrl": (channel.findtext("link") or "").strip(),
        "language": (channel.findtext("language") or "").strip(),
        "version": RSS_VERSION,
    }


def read_existing_head(output_path: Path) -> dict[str, str]:
    """Read existing OPML head values that need to be preserved across updates."""
    if not output_path.exists():
        return {}

    try:
        root = ET.parse(output_path).getroot()
    except ET.ParseError as exc:
        logger.warning("Could not parse existing OPML %s: %s", output_path, exc)
        return {}

    head = root.find("head")
    if head is None:
        return {}

    return {
        child.tag: child.text.strip()
        for child in head
        if isinstance(child.tag, str) and child.text and child.text.strip()
    }


def build_opml(repo_slug: str, created_at: str, xml_url_anchor: str) -> ET.ElementTree:
    """Build the OPML document from RSS XML files in feeds/."""
    owner = resolve_owner(repo_slug)
    opml_title = format_opml_title(repo_slug)
    opml = ET.Element("opml", {"version": "2.0"})

    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = opml_title
    ET.SubElement(head, "dateCreated").text = created_at
    ET.SubElement(head, "dateModified").text = format_opml_time(datetime.now(UTC))
    ET.SubElement(head, "ownerName").text = owner["ownerName"]
    ET.SubElement(head, "ownerEmail").text = owner["ownerEmail"]
    ET.SubElement(head, "ownerId").text = owner["ownerId"]
    ET.SubElement(head, "docs").text = OPML_DOCS_URL

    body = ET.SubElement(opml, "body")
    group = ET.SubElement(body, "outline", {"text": opml_title, "title": opml_title})

    for feed_file in sorted(get_feeds_dir().glob("feed_*.xml")):
        metadata = read_feed_metadata(feed_file, repo_slug, xml_url_anchor)
        if not metadata:
            continue

        ET.SubElement(group, "outline", metadata)

    ET.indent(opml, space="  ")
    return ET.ElementTree(opml)


def tree_to_bytes(tree: ET.ElementTree) -> bytes:
    """Serialize OPML in one consistent place for comparison and writing."""
    return ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)


def opml_signature(element: ET.Element) -> tuple:
    """Build a semantic OPML signature, ignoring head/dateModified."""
    children = []
    for child in element:
        if element.tag == "head" and child.tag == "dateModified":
            continue
        children.append(opml_signature(child))

    return (
        element.tag,
        tuple(sorted(element.attrib.items())),
        (element.text or "").strip(),
        tuple(children),
    )


def existing_content_matches(output_path: Path, candidate_tree: ET.ElementTree) -> bool:
    """Return True when existing OPML content matches the candidate, ignoring dateModified."""
    if not output_path.exists():
        return False

    try:
        existing_root = ET.parse(output_path).getroot()
    except ET.ParseError as exc:
        logger.warning("Could not parse existing OPML %s: %s", output_path, exc)
        return False

    return opml_signature(existing_root) == opml_signature(candidate_tree.getroot())


def write_opml(tree: ET.ElementTree, output_path: Path) -> None:
    """Write the OPML document to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(tree_to_bytes(tree))
    logger.info("Saved OPML to %s", output_path)


def generate_opml(output_path: Path, repo_slug: str, xml_url_anchor: str) -> None:
    """Generate or update an OPML file."""
    now = format_opml_time(datetime.now(UTC))
    existing_head = read_existing_head(output_path)
    existing_date_created = existing_head.get("dateCreated", now)

    candidate_tree = build_opml(repo_slug=repo_slug, created_at=existing_date_created, xml_url_anchor=xml_url_anchor)
    if existing_head.get("dateCreated") and existing_content_matches(output_path, candidate_tree):
        logger.info("OPML content is unchanged; preserving dateModified")
        return

    write_opml(candidate_tree, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an OPML file for all registered RSS feeds")
    parser.add_argument(
        "--output",
        type=Path,
        default=get_project_root() / DEFAULT_OUTPUT,
        help=f"Output OPML path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--repo-slug",
        default=GlobalSettings().repo_slug,
        help="GitHub repo slug used for raw feed URLs (default: RSS_REPO_SLUG or Olshansk/rss-feeds)",
    )
    parser.add_argument(
        "--xml-url-anchor",
        default=DEFAULT_XML_URL_ANCHOR,
        help="Anchor fragment appended to OPML xmlUrl values (default: empty)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_opml(output_path=args.output, repo_slug=args.repo_slug, xml_url_anchor=args.xml_url_anchor)


if __name__ == "__main__":
    main()
