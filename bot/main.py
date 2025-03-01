# bot/main.py
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from bot.handlers import start, register, help_command, check_orders, handle_message, sales_report, add_product_command, \
    load_products_command, import_costs_command
from services.scheduler import start_scheduler, scheduler
from config.config import BOT_KEY

logging.basicConfig(
    level=logging.INFO,
    filename='logs/bot.log',
    encoding='utf-8',  # Явно указываем UTF-8
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    application = Application.builder().token(BOT_KEY).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("check_orders", check_orders))
    application.add_handler(CommandHandler("sales_report", sales_report))
    application.add_handler(CommandHandler("add_product", add_product_command))
    application.add_handler(CommandHandler("load_products", load_products_command))
    application.add_handler(CommandHandler("import_costs", import_costs_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.job_queue.run_once(start_scheduler, 0)

    logging.info("Starting bot...")
    try:
        application.run_polling()
    except KeyboardInterrupt:
        logging.info("Shutting down bot...")
        application.stop()
        scheduler.shutdown()

if __name__ == "__main__":
    main()