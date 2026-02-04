from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot

from config import (
    TELEGRAM_CHAT_ID,
    DIGEST_COUNT,
    DIGEST_ENABLED,
    DAILY_QUOTE_ENABLED,
    get_digest_schedule,
    get_daily_quote_schedule,
)
from src.database import get_random_quotes, get_quote_count
from src.bot import format_quote


scheduler = AsyncIOScheduler()


async def send_digest(bot: Bot):
    """Send the weekly digest to the user."""
    quotes = await get_random_quotes(DIGEST_COUNT)
    total = await get_quote_count()

    if not quotes:
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="Your Weekly Quote Digest\n\nNo quotes saved yet. Start sending me quotes to build your collection!"
        )
        return

    message = "Your Weekly Quote Digest\n\n"

    for i, quote in enumerate(quotes, 1):
        message += f"{i}. {format_quote(quote)}\n\n"

    message += f"Total saved: {total} quotes"

    # Telegram has a 4096 character limit
    if len(message) > 4000:
        message = message[:3997] + "..."

    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


async def send_daily_quote(bot: Bot):
    """Send a single quote of the day."""
    quotes = await get_random_quotes(1)

    if not quotes:
        return  # Don't send anything if no quotes saved

    quote = quotes[0]
    message = f"Quote of the Day\n\n{format_quote(quote)}"

    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


def setup_scheduler(bot: Bot):
    """Set up the scheduled jobs."""

    # Weekly digest
    if DIGEST_ENABLED:
        schedule = get_digest_schedule()
        scheduler.add_job(
            send_digest,
            trigger="cron",
            day_of_week=schedule["day_of_week"],
            hour=schedule["hour"],
            minute=schedule["minute"],
            args=[bot],
            id="weekly_digest",
            replace_existing=True,
        )

    # Daily quote of the day
    if DAILY_QUOTE_ENABLED:
        daily_schedule = get_daily_quote_schedule()
        scheduler.add_job(
            send_daily_quote,
            trigger="cron",
            hour=daily_schedule["hour"],
            minute=daily_schedule["minute"],
            args=[bot],
            id="daily_quote",
            replace_existing=True,
        )

    scheduler.start()
