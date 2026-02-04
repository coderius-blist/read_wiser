import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ArticleMetadata:
    title: str | None
    author: str | None
    domain: str


async def fetch_metadata(url: str) -> ArticleMetadata:
    """
    Fetch article metadata from a URL.

    Extracts title, author, and domain from the page.
    """
    domain = urlparse(url).netloc.replace("www.", "")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=5.0) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ReadWiser/1.0)"
            })
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        title = _extract_title(soup)
        author = _extract_author(soup)

        return ArticleMetadata(title=title, author=author, domain=domain)

    except Exception:
        return ArticleMetadata(title=None, author=None, domain=domain)


def _extract_title(soup: BeautifulSoup) -> str | None:
    # Try og:title first (usually cleaner)
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    # Fall back to <title> tag
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        return title_tag.string.strip()

    return None


def _extract_author(soup: BeautifulSoup) -> str | None:
    # Try various meta tags
    author_selectors = [
        ("meta", {"name": "author"}),
        ("meta", {"property": "article:author"}),
        ("meta", {"property": "og:article:author"}),
        ("meta", {"name": "twitter:creator"}),
    ]

    for tag, attrs in author_selectors:
        element = soup.find(tag, attrs)
        if element and element.get("content"):
            return element["content"].strip()

    # Try common author elements
    author_classes = ["author", "byline", "author-name", "post-author"]
    for cls in author_classes:
        element = soup.find(class_=cls)
        if element and element.get_text(strip=True):
            text = element.get_text(strip=True)
            # Clean up common prefixes
            for prefix in ["By ", "by ", "Written by ", "Author: "]:
                if text.startswith(prefix):
                    text = text[len(prefix):]
            return text

    return None
