import re
from dataclasses import dataclass


@dataclass
class ParsedMessage:
    quote: str
    url: str | None
    tags: list[str]


URL_PATTERN = re.compile(r'https?://\S+')
TAG_PATTERN = re.compile(r'#(\w+)')


def parse_message(text: str) -> ParsedMessage:
    """
    Parse a message to extract quote, URL, and tags.

    Examples:
        "Be the change you wish to see"
        → quote="Be the change you wish to see", url=None, tags=[]

        "Be the change" https://example.com #wisdom
        → quote="Be the change", url="https://example.com", tags=["wisdom"]
    """
    # Extract URL
    url_match = URL_PATTERN.search(text)
    url = url_match.group(0) if url_match else None

    # Extract tags
    tags = TAG_PATTERN.findall(text)

    # Remove URL and tags from text to get the quote
    quote = text
    if url:
        quote = quote.replace(url, "")
    for tag in tags:
        quote = quote.replace(f"#{tag}", "")

    # Clean up the quote
    quote = quote.strip()
    # Remove surrounding quotes if present
    if (quote.startswith('"') and quote.endswith('"')) or \
       (quote.startswith("'") and quote.endswith("'")):
        quote = quote[1:-1].strip()

    # Remove multiple spaces
    quote = re.sub(r'\s+', ' ', quote)

    return ParsedMessage(quote=quote, url=url, tags=tags)
