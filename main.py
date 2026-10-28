def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Add it in Render Environment."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)

        # Increase connection timeouts
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)

        # Increase polling timeouts
        .get_updates_connect_timeout(30)
        .get_updates_read_timeout(40)
        .get_updates_write_timeout(30)
        .get_updates_pool_timeout(30)

        .build()
    )

    # Register bot commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("risk", risk_command))
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Starting @f0rextradingbot...")

    # Retry startup if Telegram temporarily fails to respond
    application.run_polling(
        poll_interval=2,
        timeout=20,
        bootstrap_retries=-1,
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    main()
