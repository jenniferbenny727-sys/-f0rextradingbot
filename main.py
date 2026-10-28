import os
import logging
from datetime import datetime, timezone

import httpx
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ---------------- CONFIGURATION ----------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MARKET_DATA_API_KEY = os.getenv("MARKET_DATA_API_KEY", "").strip()

API_URL = "https://api.twelvedata.com/time_series"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
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

INTERVALS = {
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1day",
}


# ---------------- MAIN MENU ----------------

def main_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "📊 Market Analysis",
                callback_data="analysis",
            )
        ],
        [
            InlineKeyboardButton(
                "💹 Forex Pairs",
                callback_data="pairs",
            ),
            InlineKeyboardButton(
                "🛡 Risk Calculator",
                callback_data="risk",
            ),
        ],
        [
            InlineKeyboardButton(
                "ℹ️ Help",
                callback_data="help",
            ),
            InlineKeyboardButton(
                "🤖 Bot Status",
                callback_data="status",
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def pair_menu():
    keyboard = []
    items = list(PAIRS.items())

    for i in range(0, len(items), 2):
        row = []
        for key, pair in items[i:i + 2]:
            row.append(
                InlineKeyboardButton(
                    pair,
                    callback_data=f"pair:{key}",
                )
            )
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("⬅️ Main Menu", callback_data="home")
    ])

    return InlineKeyboardMarkup(keyboard)


def timeframe_menu(pair_key):
    keyboard = [
        [
            InlineKeyboardButton(
                label,
                callback_data=f"analyze:{pair_key}:{label}",
            )
            for label in ("15m", "1h")
        ],
        [
            InlineKeyboardButton(
                label,
                callback_data=f"analyze:{pair_key}:{label}",
            )
            for label in ("4h", "1d")
        ],
        [
            InlineKeyboardButton("⬅️ Forex Pairs", callback_data="pairs")
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name if user else "Trader"

    await update.effective_message.reply_text(
        f"👋 Welcome, {name}!\n\n"
        "🤖 FOREX TRADING ASSISTANT\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Analyze currency pairs, review technical indicators, "
        "and calculate trading risk.\n\n"
        "📊 Market analysis\n"
        "💹 Currency pair selection\n"
        "🛡 Position risk calculations\n\n"
        "Choose an option below to get started.\n\n"
        "⚠️ Trading involves risk. No signal guarantees profit.",
        reply_markup=main_menu(),
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "📚 HOW TO USE THIS BOT\n\n"
        "/start — Open the main menu\n"
        "/help — Show these instructions\n"
        "/status — Check bot status\n"
        "/analyze EUR/USD 1h — Analyze a currency pair\n"
        "/risk 1000 1 20 10 — Calculate estimated position size\n\n"
        "Risk command format:\n"
        "/risk balance risk_percent stop_loss_pips pip_value_per_lot\n\n"
        "Example: /risk 1000 1 20 10\n"
        "This example assumes a USD-denominated account and "
        "a pip value of $10 per standard lot.\n\n"
        "Live analysis requires a configured market-data API key."
    )


async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    market_status = (
        "API key configured"
        if MARKET_DATA_API_KEY
        else "API key missing — live analysis unavailable"
    )

    await update.effective_message.reply_text(
        "🤖 Bot process is responding.\n"
        f"📡 Market data: {market_status}\n"
        "ℹ️ This status does not guarantee that the external "
        "market-data service is available."
    )


# ---------------- MARKET ANALYSIS ----------------

async def fetch_candles(symbol, interval):
    if not MARKET_DATA_API_KEY:
        raise RuntimeError(
            "Live market data is not configured. "
            "Add MARKET_DATA_API_KEY in Render Environment."
        )

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": 60,
        "apikey": MARKET_DATA_API_KEY,
        "timezone": "UTC",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(API_URL, params=params)
        response.raise_for_status()
        data = response.json()

    if data.get("status") == "error" or not data.get("values"):
        message = data.get("message", "No candle data returned.")
        raise RuntimeError(message)

    candles = []

    for item in data["values"]:
        try:
            close = float(item["close"])
            stamp = datetime.strptime(
                item["datetime"], "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=timezone.utc)

            if close > 0:
                candles.append({
                    "close": close,
                    "time": stamp,
                })
        except (ValueError, KeyError, TypeError):
            continue

    # Twelve Data normally returns newest candles first.
    candles.sort(key=lambda candle: candle["time"])

    if len(candles) < 50:
        raise RuntimeError(
            "Not enough valid candles for this analysis."
        )

    return candles


def calculate_rsi(prices, period=14):
    changes = [
        prices[i] - prices[i - 1]
        for i in range(1, len(prices))
    ]

    recent = changes[-period:]
    gains = sum(max(change, 0) for change in recent) / period
    losses = sum(max(-change, 0) for change in recent) / period

    if losses == 0:
        return 100.0 if gains > 0 else 50.0

    relative_strength = gains / losses
    return 100 - (100 / (1 + relative_strength))


async def analyze_market(symbol, interval):
    candles = await fetch_candles(symbol, interval)
    prices = [candle["close"] for candle in candles]

    latest = candles[-1]
    age_seconds = (
        datetime.now(timezone.utc) - latest["time"]
    ).total_seconds()

    # Refuse to create a directional signal from stale candles.
    interval_seconds = {
        "15min": 15 * 60,
        "1h": 60 * 60,
        "4h": 4 * 60 * 60,
        "1day": 24 * 60 * 60,
    }[interval]

    if age_seconds < -300 or age_seconds > interval_seconds * 3:
        return (
            f"📊 {symbol} — {interval}\n\n"
            "⚠️ The latest available candle is too old or has "
            "an unexpected timestamp. No signal generated.\n"
            f"Last candle: {latest['time'].isoformat()}"
        )

    sma20 = sum(prices[-20:]) / 20
    sma50 = sum(prices[-50:]) / 50
    rsi = calculate_rsi(prices)

    if sma20 > sma50 and 50 < rsi < 70:
        signal = "BUY BIAS"
        explanation = "Short-term average is above the longer-term average."
    elif sma20 < sma50 and 30 < rsi < 50:
        signal = "SELL BIAS"
        explanation = "Short-term average is below the longer-term average."
    else:
        signal = "NO TRADE"
        explanation = "The selected indicator conditions do not align."

    return (
        f"📊 MARKET ANALYSIS: {symbol}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🕒 Timeframe: {interval}\n"
        f"💲 Latest candle close: {latest['close']:.5f}\n"
        f"📈 SMA 20: {sma20:.5f}\n"
        f"📉 SMA 50: {sma50:.5f}\n"
        f"📊 RSI 14: {rsi:.2f}\n\n"
        f"🔎 Assessment: {signal}\n"
        f"📝 Reason: {explanation}\n"
        f"🕐 Candle timestamp (UTC): {latest['time'].isoformat()}\n\n"
        "Source: Twelve Data\n"
        "⚠️ Educational indicator rules, not a validated "
        "trading strategy. Confirm prices with your broker. "
        "No guaranteed results."
    )


async def analyze_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if len(context.args) != 2:
        await update.effective_message.reply_text(
            "Usage: /analyze EUR/USD 1h\n"
            "Supported timeframes: 15m, 1h, 4h, 1d"
        )
        return

    pair_input = context.args[0].upper().replace("-", "/")
    interval_input = context.args[1].lower()

    if pair_input not in PAIRS.values() or interval_input not in INTERVALS:
        await update.effective_message.reply_text(
            "Unsupported pair or timeframe. Try:\n"
            "/analyze EUR/USD 1h"
        )
        return

    await update.effective_message.reply_text(
        "⏳ Retrieving market data and analyzing..."
    )

    try:
        result = await analyze_market(
            pair_input,
            INTERVALS[interval_input],
        )
        await update.effective_message.reply_text(result)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.warning("Market analysis unavailable: %s", exc)
        await update.effective_message.reply_text(
            f"⚠️ Analysis unavailable: {str(exc)[:300]}"
        )
    except Exception:
        logger.exception("Unexpected analysis error")
        await update.effective_message.reply_text(
            "Something went wrong while analyzing the market. "
            "Please try again later."
        )


# ---------------- RISK CALCULATOR ----------------

async def risk_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if len(context.args) != 4:
        await update.effective_message.reply_text(
            "Usage:\n"
            "/risk balance risk_percent stop_loss_pips pip_value_per_lot\n\n"
            "Example:\n/risk 1000 1 20 10\n\n"
            "The pip value must be expressed in your account "
            "currency per standard lot."
        )
        return

    try:
        balance, risk_percent, stop_pips, pip_value = map(
            float, context.args
        )

        if (
            balance <= 0
            or not 0 < risk_percent <= 100
            or stop_pips <= 0
            or pip_value <= 0
        ):
            raise ValueError("All inputs must be positive and valid.")

        risk_amount = balance * risk_percent / 100
        standard_lots = risk_amount / (stop_pips * pip_value)

        await update.effective_message.reply_text(
            "🛡 RISK CALCULATOR\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"Account balance: {balance:,.2f}\n"
            f"Risk percentage: {risk_percent:g}%\n"
            f"Estimated risk amount: {risk_amount:,.2f}\n"
            f"Stop-loss distance: {stop_pips:g} pips\n"
            f"Pip value per standard lot: {pip_value:,.4f}\n"
            f"Estimated position size: {standard_lots:.3f} lots\n\n"
            "This is a mathematical estimate. Verify pip value, "
            "contract size, broker lot limits, commissions, and "
            "slippage before placing a trade."
        )

    except ValueError as exc:
        await update.effective_message.reply_text(
            f"Invalid input: {exc}\nExample: /risk 1000 1 20 10"
        )


# ---------------- BUTTON HANDLERS ----------------

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    action = query.data

    if action == "home":
        await query.edit_message_text(
            "🤖 FOREX TRADING ASSISTANT\n\nChoose an option:",
            reply_markup=main_menu(),
        )

    elif action == "pairs":
        await query.edit_message_text(
            "💹 Choose a currency pair:",
            reply_markup=pair_menu(),
        )

    elif action.startswith("pair:"):
        pair_key = action.split(":", 1)[1]

        if pair_key not in PAIRS:
            await query.edit_message_text("Invalid currency pair.")
            return

        await query.edit_message_text(
            f"Choose a timeframe for {PAIRS[pair_key]}:",
            reply_markup=timeframe_menu(pair_key),
        )

    elif action.startswith("analyze:"):
        _, pair_key, label = action.split(":")

        if pair_key not in PAIRS or label not in INTERVALS:
            await query.edit_message_text("Invalid analysis selection.")
            return

        await query.edit_message_text(
            f"⏳ Analyzing {PAIRS[pair_key]} ({label})..."
        )

        try:
            result = await analyze_market(
                PAIRS[pair_key],
                INTERVALS[label],
            )
            await query.message.reply_text(result)
        except Exception as exc:
            logger.warning("Button analysis failed: %s", exc)
            await query.message.reply_text(
                "⚠️ Market analysis is currently unavailable. "
                "Check your API key, data allowance, and logs."
            )

    elif action == "risk":
        await query.edit_message_text(
            "🛡 RISK CALCULATOR\n\n"
            "Send your inputs in this format:\n"
            "/risk 1000 1 20 10\n\n"
            "Balance, risk %, stop-loss pips, pip value per lot."
        )

    elif action == "help":
        await query.edit_message_text(
            "Commands:\n"
            "/start — Main menu\n"
            "/analyze EUR/USD 1h — Market analysis\n"
            "/risk 1000 1 20 10 — Risk calculation\n"
            "/status — Bot status\n"
            "/help — Help",
            reply_markup=main_menu(),
        )

    elif action == "status":
        api_status = (
            "Configured" if MARKET_DATA_API_KEY else "Not configured"
        )
        await query.edit_message_text(
            "🤖 Bot is responding.\n"
            f"Market-data API key: {api_status}\n"
            "External API availability is not guaranteed.",
            reply_markup=main_menu(),
        )


# ---------------- START APPLICATION ----------------

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Add it to your environment variables."
        )

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("risk", risk_command))
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Starting Forex Telegram bot...")
    application.run_polling()


if __name__ == "__main__":
    main()
