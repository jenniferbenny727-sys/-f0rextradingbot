import os
import logging
from datetime import datetime, timezone

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =====================================================
# CONFIGURATION
# =====================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MARKET_DATA_API_KEY = os.getenv("MARKET_DATA_API_KEY", "").strip()

API_URL = "https://api.twelvedata.com/time_series"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

# Avoid verbose HTTP logs that could expose request details.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

PAIRS = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD",
    "USDCHF": "USD/CHF",
    "NZDUSD": "NZD/USD",
}

TIMEFRAMES = {
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1day",
}


# =====================================================
# MENUS
# =====================================================

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📊 Market Analysis",
                callback_data="pairs",
            )
        ],
        [
            InlineKeyboardButton(
                "🛡 Risk Calculator",
                callback_data="risk",
            ),
            InlineKeyboardButton(
                "📚 Forex Education",
                callback_data="education",
            ),
        ],
        [
            InlineKeyboardButton(
                "🤖 Bot Status",
                callback_data="status",
            ),
            InlineKeyboardButton(
                "ℹ️ Help",
                callback_data="help",
            ),
        ],
    ])


def pair_menu():
    rows = []
    pair_items = list(PAIRS.items())

    for index in range(0, len(pair_items), 2):
        row = []

        for key, name in pair_items[index:index + 2]:
            row.append(
                InlineKeyboardButton(
                    name,
                    callback_data=f"pair:{key}",
                )
            )

        rows.append(row)

    rows.append([
        InlineKeyboardButton(
            "⬅️ Main Menu",
            callback_data="home",
        )
    ])

    return InlineKeyboardMarkup(rows)


def timeframe_menu(pair_key):
    rows = [
        [
            InlineKeyboardButton(
                "15 minutes",
                callback_data=f"analyze:{pair_key}:15m",
            ),
            InlineKeyboardButton(
                "1 hour",
                callback_data=f"analyze:{pair_key}:1h",
            ),
        ],
        [
            InlineKeyboardButton(
                "4 hours",
                callback_data=f"analyze:{pair_key}:4h",
            ),
            InlineKeyboardButton(
                "1 day",
                callback_data=f"analyze:{pair_key}:1d",
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Forex Pairs",
                callback_data="pairs",
            )
        ],
    ]

    return InlineKeyboardMarkup(rows)


# =====================================================
# TELEGRAM COMMANDS
# =====================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    name = user.first_name if user else "Trader"

    message = (
        f"👋 Welcome, {name}!\n\n"
        "🤖 FOREX TRADING ASSISTANT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Explore currency-pair analysis, technical indicators, "
        "risk calculations, and Forex education.\n\n"
        "📊 Market analysis\n"
        "💹 Major currency pairs\n"
        "🛡 Position-size calculator\n"
        "📚 Trading education\n\n"
        "Choose an option below to begin.\n\n"
        "⚠️ Trading involves risk. No signal guarantees profit."
    )

    await update.effective_message.reply_text(
        message,
        reply_markup=main_menu(),
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = (
        "📚 BOT HELP\n\n"
        "/start — Open the main menu\n"
        "/help — Show this help message\n"
        "/status — Check whether the bot responds\n"
        "/analyze EUR/USD 1h — Analyze a currency pair\n"
        "/risk 1000 1 20 10 — Estimate position size\n\n"
        "Supported pairs:\n"
        + ", ".join(PAIRS.values())
        + "\n\nSupported timeframes: 15m, 1h, 4h, 1d\n\n"
        "Live market analysis requires a valid market-data API key."
    )

    await update.effective_message.reply_text(
        message,
        reply_markup=main_menu(),
    )


async def about_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "🤖 About Forex Trading Assistant\n\n"
        "This bot provides technical indicator summaries, "
        "educational trading information, and risk calculations.\n\n"
        "It does not execute trades or guarantee trading results."
    )


async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    api_status = (
        "Configured"
        if MARKET_DATA_API_KEY
        else "Not configured — live analysis unavailable"
    )

    await update.effective_message.reply_text(
        "🤖 BOT STATUS\n\n"
        "✅ Telegram bot process is responding.\n"
        f"📡 Market-data API key: {api_status}\n\n"
        "Note: this checks the bot response, not the availability "
        "of every external service."
    )


# =====================================================
# MARKET DATA
# =====================================================

async def fetch_candles(symbol, interval):
    if not MARKET_DATA_API_KEY:
        raise RuntimeError(
            "Market data is not configured. Add "
            "MARKET_DATA_API_KEY in Render Environment."
        )

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": 60,
        "apikey": MARKET_DATA_API_KEY,
        "timezone": "UTC",
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(25.0, connect=10.0),
    ) as client:
        response = await client.get(API_URL, params=params)
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, dict):
        raise RuntimeError("Unexpected response from the market-data provider.")

    if data.get("status") == "error" or "values" not in data:
        # Do not log or reveal the request URL because it contains the API key.
        raise RuntimeError(
            data.get("message", "Market-data provider returned no candle data.")
        )

    candles = []

    for item in data.get("values", []):
        try:
            raw_time = item["datetime"]

            try:
                stamp = datetime.strptime(
                    raw_time,
                    "%Y-%m-%d %H:%M:%S",
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                stamp = datetime.fromisoformat(
                    raw_time.replace("Z", "+00:00")
                )

                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                else:
                    stamp = stamp.astimezone(timezone.utc)

            close = float(item["close"])

            if close > 0:
                candles.append({
                    "time": stamp,
                    "close": close,
                })

        except (ValueError, TypeError, KeyError, AttributeError):
            continue

    # Provider responses may arrive newest first.
    candles.sort(key=lambda item: item["time"])

    if len(candles) < 50:
        raise RuntimeError(
            "There are not enough valid candles to calculate the indicators."
        )

    return candles


# =====================================================
# TECHNICAL INDICATORS
# =====================================================

def calculate_rsi(prices, period=14):
    if len(prices) <= period:
        raise ValueError("Not enough prices to calculate RSI.")

    changes = [
        prices[i] - prices[i - 1]
        for i in range(1, len(prices))
    ]

    recent = changes[-period:]

    average_gain = (
        sum(max(change, 0) for change in recent) / period
    )

    average_loss = (
        sum(max(-change, 0) for change in recent) / period
    )

    if average_gain == 0 and average_loss == 0:
        return 50.0

    if average_loss == 0:
        return 100.0

    relative_strength = average_gain / average_loss

    return 100 - (100 / (1 + relative_strength))


async def analyze_market(symbol, interval):
    candles = await fetch_candles(symbol, interval)

    prices = [item["close"] for item in candles]
    latest = candles[-1]

    age_seconds = (
        datetime.now(timezone.utc) - latest["time"]
    ).total_seconds()

    interval_seconds = {
        "15min": 15 * 60,
        "1h": 60 * 60,
        "4h": 4 * 60 * 60,
        "1day": 24 * 60 * 60,
    }[interval]

    # Do not create a signal using unexpectedly stale data.
    if age_seconds < -300 or age_seconds > interval_seconds * 3:
        return (
            f"📊 {symbol} — {interval}\n\n"
            "⚠️ The latest candle appears stale or has an "
            "unexpected timestamp. No signal generated.\n"
            f"Last candle (UTC): {latest['time'].isoformat()}"
        )

    sma20 = sum(prices[-20:]) / 20
    sma50 = sum(prices[-50:]) / 50
    rsi = calculate_rsi(prices)

    if sma20 > sma50 and 50 < rsi < 70:
        signal = "BUY BIAS"
        explanation = (
            "SMA 20 is above SMA 50 and RSI indicates positive momentum."
        )

    elif sma20 < sma50 and 30 < rsi < 50:
        signal = "SELL BIAS"
        explanation = (
            "SMA 20 is below SMA 50 and RSI indicates negative momentum."
        )

    else:
        signal = "NO TRADE"
        explanation = (
            "The selected indicator conditions do not align clearly."
        )

    # Use sensible display precision for JPY and non-JPY pairs.
    price_digits = 3 if symbol.endswith("JPY") else 5

    return (
        f"📊 FOREX MARKET ANALYSIS\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💹 Pair: {symbol}\n"
        f"🕒 Timeframe: {interval}\n"
        f"💲 Latest candle close: {latest['close']:.{price_digits}f}\n"
        f"📈 SMA 20: {sma20:.{price_digits}f}\n"
        f"📉 SMA 50: {sma50:.{price_digits}f}\n"
        f"📊 RSI 14: {rsi:.2f}\n\n"
        f"🔎 Assessment: {signal}\n"
        f"📝 Reason: {explanation}\n\n"
        f"🕐 Candle time (UTC): {latest['time'].isoformat()}\n"
        f"📡 Source: Twelve Data\n\n"
        "⚠️ This is a basic technical-indicator assessment, "
        "not a validated trading strategy or a guarantee of future "
        "price direction. Confirm prices with your broker."
    )


async def analyze_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if len(context.args) != 2:
        await update.effective_message.reply_text(
            "Usage:\n/analyze EUR/USD 1h\n\n"
            "Timeframes: 15m, 1h, 4h, 1d"
        )
        return

    symbol = context.args[0].upper().replace("-", "/")
    timeframe = context.args[1].lower()

    if symbol not in PAIRS.values():
        await update.effective_message.reply_text(
            "Unsupported pair. Try /analyze EUR/USD 1h"
        )
        return

    if timeframe not in TIMEFRAMES:
        await update.effective_message.reply_text(
            "Unsupported timeframe. Choose 15m, 1h, 4h or 1d."
        )
        return

    status_message = await update.effective_message.reply_text(
        "⏳ Retrieving market data. Please wait..."
    )

    try:
        result = await analyze_market(
            symbol,
            TIMEFRAMES[timeframe],
        )

        await status_message.edit_text(result)

    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.warning("Market analysis unavailable: %s", exc)

        await status_message.edit_text(
            "⚠️ Market analysis is currently unavailable.\n\n"
            f"Reason: {str(exc)[:250]}\n\n"
            "Check your API key, provider limits, and network connection."
        )

    except Exception:
        logger.exception("Unexpected market analysis error")

        await status_message.edit_text(
            "An unexpected error occurred. Please try again later."
        )


# =====================================================
# RISK CALCULATOR
# =====================================================

async def risk_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if len(context.args) != 4:
        await update.effective_message.reply_text(
            "🛡 POSITION SIZE CALCULATOR\n\n"
            "Format:\n"
            "/risk balance risk_percent stop_loss_pips pip_value_per_lot\n\n"
            "Example:\n"
            "/risk 1000 1 20 10\n\n"
            "Assumes the pip value is in your account currency "
            "per standard lot."
        )
        return

    try:
        balance, risk_percent, stop_pips, pip_value = map(
            float,
            context.args,
        )

        if not all(map(
            lambda value: value == value
            and value not in (float("inf"), float("-inf")),
            (balance, risk_percent, stop_pips, pip_value),
        )):
            raise ValueError("Inputs must be finite numbers.")

        if balance <= 0:
            raise ValueError("Balance must be greater than zero.")

        if not 0 < risk_percent <= 100:
            raise ValueError("Risk percentage must be above 0 and at most 100.")

        if stop_pips <= 0 or pip_value <= 0:
            raise ValueError("Stop-loss pips and pip value must be positive.")

        risk_amount = balance * risk_percent / 100
        lot_size = risk_amount / (stop_pips * pip_value)

        await update.effective_message.reply_text(
            "🛡 RISK CALCULATOR\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"💰 Account balance: {balance:,.2f}\n"
            f"📊 Risk: {risk_percent:g}%\n"
            f"💵 Estimated risk amount: {risk_amount:,.2f}\n"
            f"🛑 Stop-loss: {stop_pips:g} pips\n"
            f"📍 Pip value per standard lot: {pip_value:,.4f}\n"
            f"📐 Estimated position size: {lot_size:.3f} lots\n\n"
            "Verify pip value, account currency, contract size, "
            "broker lot limits, commissions, and slippage before trading."
        )

    except ValueError as exc:
        await update.effective_message.reply_text(
            f"Invalid input: {exc}\n\n"
            "Example: /risk 1000 1 20 10"
        )


# =====================================================
# BUTTON HANDLER
# =====================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if query is None:
        return

    await query.answer()
    action = query.data or ""

    try:
        if action == "home":
            await query.edit_message_text(
                "🤖 FOREX TRADING ASSISTANT\n\nChoose an option:",
                reply_markup=main_menu(),
            )

        elif action == "pairs":
            await query.edit_message_text(
                "💹 Select a currency pair:",
                reply_markup=pair_menu(),
            )

        elif action.startswith("pair:"):
            pair_key = action.split(":", 1)[1]

            if pair_key not in PAIRS:
                await query.edit_message_text("Invalid currency pair.")
                return

            await query.edit_message_text(
                f"Select a timeframe for {PAIRS[pair_key]}:",
                reply_markup=timeframe_menu(pair_key),
            )

        elif action.startswith("analyze:"):
            parts = action.split(":")

            if len(parts) != 3:
                await query.edit_message_text("Invalid analysis selection.")
                return

            _, pair_key, timeframe = parts

            if pair_key not in PAIRS or timeframe not in TIMEFRAMES:
                await query.edit_message_text("Invalid pair or timeframe.")
                return

            await query.edit_message_text(
                f"⏳ Analyzing {PAIRS[pair_key]} ({timeframe})..."
            )

            try:
                result = await analyze_market(
                    PAIRS[pair_key],
                    TIMEFRAMES[timeframe],
                )

                await query.message.reply_text(result)

            except Exception:
                logger.exception("Analysis button failed")
                await query.message.reply_text(
                    "⚠️ Analysis is unavailable. Check the market-data "
                    "API configuration and Render logs."
                )

        elif action == "risk":
            await query.edit_message_text(
                "🛡 RISK CALCULATOR\n\n"
                "Send this command with your own values:\n"
                "/risk 1000 1 20 10\n\n"
                "Format: balance, risk %, stop-loss pips, "
                "pip value per standard lot.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "⬅️ Main Menu",
                        callback_data="home",
                    )
                ]]),
            )

        elif action == "help":
            await query.edit_message_text(
                "Commands:\n"
                "/start — Main menu\n"
                "/help — Help\n"
                "/about — About this bot\n"
                "/status — Bot status\n"
                "/analyze EUR/USD 1h — Analyze a pair\n"
                "/risk 1000 1 20 10 — Calculate position size",
                reply_markup=main_menu(),
            )

        elif action == "status":
            api_status = (
                "Configured"
                if MARKET_DATA_API_KEY
                else "Not configured"
            )

            await query.edit_message_text(
                "🤖 Bot is responding.\n"
                f"📡 Market-data API key: {api_status}\n"
                "External API availability has not been verified.",
                reply_markup=main_menu(),
            )

        elif action == "education":
            await query.edit_message_text(
                "📚 FOREX EDUCATION\n\n"
                "• Understand pips and spreads.\n"
                "• Use stop-loss orders thoughtfully.\n"
                "• Calculate position size before trading.\n"
                "• Be aware of leverage and drawdown.\n"
                "• Test strategies before using real money.\n\n"
                "Forex trading can result in losses.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "⬅️ Main Menu",
                        callback_data="home",
                    )
                ]]),
            )

        else:
            await query.edit_message_text(
                "Unknown option. Please open the main menu with /start."
            )

    except Exception:
        logger.exception("Button handler failed")
        try:
            await query.message.reply_text(
                "Something went wrong. Please send /start and try again."
            )
        except Exception:
            logger.exception("Could not send button error message")


# =====================================================
# STARTUP
# =====================================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Add it under Render Environment."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .get_updates_connect_timeout(30)
        .get_updates_read_timeout(40)
        .get_updates_write_timeout(30)
        .get_updates_pool_timeout(30)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("risk", risk_command))
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Starting @f0rextradingbot...")

    application.run_polling(
        poll_interval=2,
        timeout=20,
        bootstrap_retries=-1,
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    main()
