import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Constants for validation
MAX_QUOTE_LENGTH = 4000  # Telegram message limit is 4096, leave room for formatting
MAX_URL_LENGTH = 2048
MAX_TAG_LENGTH = 50
MAX_TAGS = 20


@dataclass
class ParsedMessage:
    quote: str
    url: str | None
    tags: list[str]


URL_PATTERN = re.compile(r'https?://\S+')
TAG_PATTERN = re.compile(r'#(\w+)')


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_url(url: str) -> str | None:
    """Validate and clean a URL. Returns None if invalid."""
    if not url:
        return None

    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        logger.warning(f"URL too long ({len(url)} chars), truncating")
        return None

    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        return None

    return url


def validate_tag(tag: str) -> str | None:
    """Validate a single tag. Returns None if invalid."""
    if not tag:
        return None

    tag = tag.strip()
    if len(tag) > MAX_TAG_LENGTH:
        logger.warning(f"Tag '{tag[:20]}...' too long, skipping")
        return None

    # Only allow alphanumeric and underscore
    if not re.match(r'^\w+$', tag):
        return None

    return tag


def parse_message(text: str) -> ParsedMessage:
    """
    Parse a message to extract quote, URL, and tags.

    Includes input validation for:
    - Quote length (max 4000 chars)
    - URL format and length
    - Tag format and count

    Examples:
        "Be the change you wish to see"
        → quote="Be the change you wish to see", url=None, tags=[]

        "Be the change" https://example.com #wisdom
        → quote="Be the change", url="https://example.com", tags=["wisdom"]

    Args:
        text: The message text to parse

    Returns:
        ParsedMessage with extracted quote, URL, and tags
    """
    # Handle empty or None input
    if not text:
        return ParsedMessage(quote="", url=None, tags=[])

    # Limit input length to prevent abuse
    if len(text) > MAX_QUOTE_LENGTH * 2:  # Allow extra for URL and tags
        logger.warning(f"Input text too long ({len(text)} chars), truncating")
        text = text[:MAX_QUOTE_LENGTH * 2]

    # Extract URL
    url_match = URL_PATTERN.search(text)
    url = None
    if url_match:
        raw_url = url_match.group(0)
        url = validate_url(raw_url)
        if url is None and raw_url:
            logger.debug(f"Invalid URL format: {raw_url[:50]}...")

    # Extract and validate tags
    raw_tags = TAG_PATTERN.findall(text)
    tags = []
    for raw_tag in raw_tags[:MAX_TAGS]:  # Limit number of tags
        validated_tag = validate_tag(raw_tag)
        if validated_tag and validated_tag not in tags:  # Avoid duplicates
            tags.append(validated_tag)

    if len(raw_tags) > MAX_TAGS:
        logger.warning(f"Too many tags ({len(raw_tags)}), using first {MAX_TAGS}")

    # Remove URL and tags from text to get the quote
    quote = text
    if url_match:
        quote = quote.replace(url_match.group(0), "")
    for tag in raw_tags:  # Remove all raw tags, even invalid ones
        quote = quote.replace(f"#{tag}", "")

    # Clean up the quote
    quote = quote.strip()

    # Remove surrounding quotes if present
    if (quote.startswith('"') and quote.endswith('"')) or \
       (quote.startswith("'") and quote.endswith("'")):
        quote = quote[1:-1].strip()

    # Remove multiple spaces
    quote = re.sub(r'\s+', ' ', quote)

    # Enforce quote length limit
    if len(quote) > MAX_QUOTE_LENGTH:
        logger.warning(f"Quote too long ({len(quote)} chars), truncating")
        quote = quote[:MAX_QUOTE_LENGTH]

    return ParsedMessage(quote=quote, url=url, tags=tags)
