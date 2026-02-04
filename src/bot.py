from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from src.database import (
    save_quote,
    delete_quote,
    get_quote_by_id,
    get_random_quotes,
    get_last_quotes,
    get_quote_count,
    get_quotes_this_week,
    search_quotes,
    get_quotes_by_tag,
    get_quotes_by_source,
    get_top_tags,
    is_duplicate,
    toggle_favorite,
    get_favorite_quotes,
    export_all_quotes,
)
from src.parser import parse_message
from src.metadata import fetch_metadata


def is_authorized(update: Update) -> bool:
    """Check if the message is from the authorized user."""
    return str(update.effective_chat.id) == str(TELEGRAM_CHAT_ID)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    await update.message.reply_text(
        "Welcome to ReadWiser!\n\n"
        "Send me quotes to save them. You can include:\n"
        "- Just the quote text\n"
        "- Quote + URL (I'll fetch the article title)\n"
        "- #tags to categorize\n\n"
        "Example:\n"
        '"The best time to plant a tree was 20 years ago" '
        "https://example.com #wisdom\n\n"
        "Commands:\n"
        "/random - Get a random quote\n"
        "/last - Show recently saved quotes\n"
        "/digest - Get your digest now\n"
        "/stats - View your statistics\n\n"
        "Search:\n"
        "/search <word> - Search in quotes\n"
        "/tag <name> - Find by tag\n"
        "/source <domain> - Find by source\n\n"
        "Manage:\n"
        "/fav <id> - Toggle favorite\n"
        "/favorites - Show all favorites\n"
        "/delete <id> - Delete a quote\n"
        "/export - Export all quotes as JSON"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await start_command(update, context)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    total = await get_quote_count()
    this_week = await get_quotes_this_week()
    favorites = len(await get_favorite_quotes())
    top_tags = await get_top_tags(5)

    tags_text = ""
    if top_tags:
        tags_text = "\n\nTop tags:\n" + "\n".join(
            f"  #{tag}: {count}" for tag, count in top_tags
        )

    await update.message.reply_text(
        f"Your ReadWiser Stats\n\n"
        f"Total quotes: {total}\n"
        f"Added this week: {this_week}\n"
        f"Favorites: {favorites}"
        f"{tags_text}"
    )


async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    quotes = await get_random_quotes(1)
    if not quotes:
        await update.message.reply_text("No quotes saved yet. Send me some!")
        return

    quote = quotes[0]
    await update.message.reply_text(format_quote(quote, show_id=True))


async def last_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    n = 5
    if context.args:
        try:
            n = min(int(context.args[0]), 10)
        except ValueError:
            pass

    quotes = await get_last_quotes(n)
    if not quotes:
        await update.message.reply_text("No quotes saved yet.")
        return

    response = f"Last {len(quotes)} quote(s):\n\n"
    for quote in quotes:
        response += f"{format_quote(quote, show_id=True)}\n\n"

    await update.message.reply_text(response[:4000])


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /search <keyword>")
        return

    keyword = " ".join(context.args)
    quotes = await search_quotes(keyword)

    if not quotes:
        await update.message.reply_text(f'No quotes found containing "{keyword}"')
        return

    response = f'Found {len(quotes)} quote(s) for "{keyword}":\n\n'
    for quote in quotes[:5]:
        response += f"{format_quote(quote, show_id=True)}\n\n"

    await update.message.reply_text(response[:4000])


async def tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /tag <tagname>")
        return

    tag = context.args[0].lstrip("#")
    quotes = await get_quotes_by_tag(tag)

    if not quotes:
        await update.message.reply_text(f'No quotes found with tag #{tag}')
        return

    response = f'Found {len(quotes)} quote(s) with #{tag}:\n\n'
    for quote in quotes[:5]:
        response += f"{format_quote(quote, show_id=True)}\n\n"

    await update.message.reply_text(response[:4000])


async def source_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /source <domain>")
        return

    domain = context.args[0]
    quotes = await get_quotes_by_source(domain)

    if not quotes:
        await update.message.reply_text(f'No quotes found from {domain}')
        return

    response = f'Found {len(quotes)} quote(s) from {domain}:\n\n'
    for quote in quotes[:5]:
        response += f"{format_quote(quote, show_id=True)}\n\n"

    await update.message.reply_text(response[:4000])


async def fav_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /fav <quote_id>")
        return

    try:
        quote_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid quote ID. Use a number.")
        return

    result = await toggle_favorite(quote_id)
    if result is None:
        await update.message.reply_text(f"Quote #{quote_id} not found.")
        return

    status = "added to" if result else "removed from"
    await update.message.reply_text(f"Quote #{quote_id} {status} favorites.")


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    quotes = await get_favorite_quotes()
    if not quotes:
        await update.message.reply_text("No favorite quotes yet. Use /fav <id> to add some!")
        return

    response = f"Your {len(quotes)} favorite quote(s):\n\n"
    for quote in quotes[:10]:
        response += f"{format_quote(quote, show_id=True)}\n\n"

    if len(quotes) > 10:
        response += f"... and {len(quotes) - 10} more"

    await update.message.reply_text(response[:4000])


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /delete <quote_id>")
        return

    try:
        quote_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid quote ID. Use a number.")
        return

    quote = await get_quote_by_id(quote_id)
    if not quote:
        await update.message.reply_text(f"Quote #{quote_id} not found.")
        return

    success = await delete_quote(quote_id)
    if success:
        await update.message.reply_text(
            f"Deleted quote #{quote_id}:\n\"{truncate(quote['text'], 50)}\""
        )
    else:
        await update.message.reply_text("Failed to delete quote.")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    json_data = await export_all_quotes()
    count = await get_quote_count()

    if count == 0:
        await update.message.reply_text("No quotes to export.")
        return

    # Send as a document
    from io import BytesIO
    file = BytesIO(json_data.encode())
    file.name = "readwiser_quotes.json"

    await update.message.reply_document(
        document=file,
        caption=f"Exported {count} quotes"
    )


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    from src.scheduler import send_digest
    await send_digest(context.bot)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    text = update.message.text
    if not text:
        return

    parsed = parse_message(text)

    if not parsed.quote:
        await update.message.reply_text(
            "I couldn't find a quote in your message. "
            "Send me some text to save!"
        )
        return

    # Check for duplicates
    if await is_duplicate(parsed.quote):
        await update.message.reply_text("This quote was already saved recently.")
        return

    # Fetch metadata if URL provided
    title, author, domain = None, None, None
    if parsed.url:
        metadata = await fetch_metadata(parsed.url)
        title = metadata.title
        author = metadata.author
        domain = metadata.domain

    # Save to database
    quote_id = await save_quote(
        text=parsed.quote,
        url=parsed.url,
        title=title,
        author=author,
        domain=domain,
        tags=parsed.tags,
    )

    # Build confirmation message
    response = f'Saved (#{quote_id}): "{truncate(parsed.quote, 100)}"'

    if title or domain:
        source = title or domain
        if author:
            source += f" by {author}"
        elif domain and title:
            source += f" ({domain})"
        response += f"\nFrom: {source}"

    if parsed.tags:
        response += f"\nTags: {' '.join(f'#{t}' for t in parsed.tags)}"

    await update.message.reply_text(response)


def format_quote(quote: dict, show_id: bool = False) -> str:
    """Format a quote for display."""
    prefix = f"[#{quote['id']}] " if show_id else ""
    fav = " *" if quote.get("is_favorite") else ""
    text = f'{prefix}"{quote["text"]}"{fav}'

    source_parts = []
    if quote.get("source_title"):
        source_parts.append(quote["source_title"])
    if quote.get("source_author"):
        source_parts.append(f"by {quote['source_author']}")
    elif quote.get("source_domain"):
        source_parts.append(f"({quote['source_domain']})")

    if source_parts:
        text += f"\n  -- {' '.join(source_parts)}"

    if quote.get("url"):
        text += f"\n  {quote['url']}"

    if quote.get("tags"):
        text += f"\n  {' '.join(f'#{t}' for t in quote['tags'].split(','))}"

    return text


def truncate(text: str, length: int) -> str:
    """Truncate text to length with ellipsis."""
    if len(text) <= length:
        return text
    return text[:length - 3] + "..."


def create_bot() -> Application:
    """Create and configure the Telegram bot."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("random", random_command))
    app.add_handler(CommandHandler("last", last_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("tag", tag_command))
    app.add_handler(CommandHandler("source", source_command))
    app.add_handler(CommandHandler("fav", fav_command))
    app.add_handler(CommandHandler("favorites", favorites_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CommandHandler("digest", digest_command))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
